import threading
import time
import random
from cloudflare_api import CloudflareAPI
from logger import app_logger
import export_utils

class QueueManager:
    def __init__(self, config, domains, ip_address, update_gui_callback, mode="point"):
        self.config = config
        self.domains = domains # List of dicts: {'domain': '...', 'ip': '...', 'profile': '...', 'status': '...', 'nameservers': '', 'error': ''}
        self.ip_address = ip_address
        self.update_gui_callback = update_gui_callback
        self.mode = mode # "point" or "update_ip"
        
        self.api_clients = {}
        self.batch_size = config.get('batch_size', 5)
        self.delay_req = config.get('delay_between_requests', [2, 5])
        self.delay_batch = config.get('delay_between_batches', [30, 60])
        self.max_retries = config.get('max_retries', 3)
        
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        self.thread = None

    def _get_api_for_item(self, item):
        prof_name = item.get('profile') or self.config.get('current_profile', 'Default')
        if prof_name not in self.api_clients:
            self.api_clients[prof_name] = CloudflareAPI(self.config, profile_name=prof_name)
        return self.api_clients[prof_name], prof_name

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.is_paused = False
        self.should_stop = False
        self.thread = threading.Thread(target=self._process_queue)
        self.thread.start()

    def pause(self):
        self.is_paused = True
        app_logger.info("Processing paused.")

    def resume(self):
        self.is_paused = False
        app_logger.info("Processing resumed.")

    def stop(self):
        self.should_stop = True
        app_logger.info("Stopping process...")

    def _sleep(self, duration):
        # Sleep in small increments to allow quick stopping/pausing
        end_time = time.time() + duration
        while time.time() < end_time:
            if self.should_stop:
                return False
            time.sleep(0.1)
        return True
        
    def _wait_if_paused(self):
        while self.is_paused and not self.should_stop:
            time.sleep(0.5)

    def _process_queue(self):
        action_name = "Updating IP" if self.mode == "update_ip" else "Starting domain processing"
        
        pending_items = [d for d in self.domains if self.mode == "update_ip" or d.get('status') != 'Success']
        if not pending_items:
            app_logger.info("Semua domain dalam antrian sudah berstatus Success. Tidak ada domain pending untuk diproses.")
            self.is_running = False
            self.update_gui_callback()
            return
            
        app_logger.info(f"{action_name} untuk {len(pending_items)} domain pending (total antrian: {len(self.domains)})...")
        
        # Determine profiles used and test connections
        required_profiles = set()
        for item in pending_items:
            p_name = item.get('profile') or self.config.get('current_profile', 'Default')
            required_profiles.add(p_name)

        failed_profiles = []
        for p_name in required_profiles:
            api_client, _ = self._get_api_for_item({'profile': p_name})
            success, msg = api_client.test_connection()
            if not success:
                app_logger.error(f"API Connection failed for profile '{p_name}': {msg}")
                failed_profiles.append(p_name)
            else:
                app_logger.info(f"API Connection successful for profile '{p_name}'.")

        if len(failed_profiles) == len(required_profiles):
            app_logger.error("Semua profil API Cloudflare gagal melakukan koneksi.")
            self.is_running = False
            self.update_gui_callback()
            return

        batch_count = 0
        domains_processed_in_batch = 0
        
        for idx, item in enumerate(self.domains):
            self._wait_if_paused()
            if self.should_stop:
                break
                
            if self.mode == "point" and item.get('status') == 'Success':
                continue # Skip already processed

            domain = item['domain']
            target_ip = item.get('ip') or self.ip_address
            api_client, prof_name = self._get_api_for_item(item)
            item['profile'] = prof_name
            
            if self.mode == "update_ip":
                app_logger.info(f"Updating IP for: {domain} -> {target_ip} (CF Profile: {prof_name})")
            else:
                app_logger.info(f"Processing: {domain} -> {target_ip} (CF Profile: {prof_name})")

            item['status'] = 'Processing'
            self.update_gui_callback()
            
            if self.mode == "update_ip":
                success = self._update_single_domain_ip(domain, item, target_ip, api_client)
            else:
                success = self._process_single_domain(domain, item, target_ip, api_client)
            
            if success:
                item['status'] = 'Success'
                item['error'] = ''
            else:
                item['status'] = 'Failed'
                
            export_utils.save_state(self.domains)
            self.update_gui_callback()
            
            domains_processed_in_batch += 1
            
            # Check if batch limit reached (if batch_size > 0)
            if self.batch_size > 0 and domains_processed_in_batch >= self.batch_size:
                domains_processed_in_batch = 0
                batch_count += 1
                delay = random.randint(self.delay_batch[0], self.delay_batch[1])
                app_logger.info(f"[Batch {batch_count} Selesai] Memproses {self.batch_size} domain. Istirahat selama {delay} detik sebelum batch berikutnya...")
                if not self._sleep(delay):
                    break
            else:
                # Normal delay between requests
                delay = random.randint(self.delay_req[0], self.delay_req[1])
                if not self._sleep(delay):
                    break

        app_logger.info("Processing queue finished or stopped.")
        self.is_running = False
        self.update_gui_callback()

    def _update_single_domain_ip(self, domain, item, target_ip, api_client):
        retries = 0
        while retries <= self.max_retries:
            self._wait_if_paused()
            if self.should_stop:
                return False
                
            if retries > 0:
                app_logger.warning(f"Retrying IP update for {domain} (Attempt {retries}/{self.max_retries})")
                self._sleep(5)

            success, ns, msg = api_client.update_domain_ip(domain, target_ip)
            if success:
                if ns:
                    item['nameservers'] = ", ".join(ns)
                app_logger.info(f"[{domain}] IP successfully updated to {target_ip}")
                return True
            else:
                item['error'] = f"Update IP: {msg}"
                app_logger.error(f"[{domain}] Failed to update IP: {msg}")
                retries += 1

        return False

    def _process_single_domain(self, domain, item, target_ip, api_client):
        # Determine root domain and whether to force WWW
        if domain.startswith("www."):
            root_domain = domain[4:]
            force_www = True
        else:
            root_domain = domain
            force_www = False
            
        retries = 0
        while retries <= self.max_retries:
            self._wait_if_paused()
            if self.should_stop:
                return False
                
            if retries > 0:
                app_logger.warning(f"Retrying {domain} (Attempt {retries}/{self.max_retries})")
                self._sleep(5) # Base delay for retry

            # 1. Add Zone using root domain
            success, data, msg = api_client.add_zone(root_domain)
            if not success:
                item['error'] = f"Add Zone: {msg}"
                app_logger.error(f"[{domain}] Failed to add zone: {msg}")
                if "already exists" not in msg.lower() and "rate limit" not in msg.lower():
                    pass
                retries += 1
                continue
            
            zone_id = data['zone_id']
            ns = data.get('name_servers', [])
            item['nameservers'] = ", ".join(ns)
            app_logger.info(f"[{domain}] Zone added. NS: {item['nameservers']}")
            
            self._sleep(random.uniform(1.0, 2.0))

            # 2. Add DNS A Record using root domain and target_ip
            success, msg = api_client.add_dns_record(zone_id, "A", root_domain, target_ip, proxied=True)
            if not success:
                item['error'] = f"A Record: {msg}"
                app_logger.error(f"[{domain}] Failed to add A record: {msg}")

            self._sleep(random.uniform(1.0, 2.0))

            # 3. Add CNAME (if www is checked OR if user typed www. in the domain)
            if force_www:
                success, msg = api_client.add_dns_record(zone_id, "CNAME", f"www.{root_domain}", root_domain, proxied=True)
                if not success:
                    app_logger.error(f"[{domain}] Failed to add CNAME record: {msg}")
                self._sleep(random.uniform(1.0, 2.0))
                
            # 4. Set SSL Flexible
            success, msg = api_client.set_ssl_flexible(zone_id)
            if not success:
                app_logger.error(f"[{domain}] Failed to set SSL: {msg}")
            self._sleep(random.uniform(1.0, 2.0))

            # 5. Set Always Use HTTPS
            success, msg = api_client.set_always_use_https(zone_id)
            if not success:
                app_logger.error(f"[{domain}] Failed to set Always Use HTTPS: {msg}")

            app_logger.info(f"[{domain}] Successfully configured to IP {target_ip}.")
            return True
            
        return False
