import requests
import json
from logger import app_logger

BASE_URL = "https://api.cloudflare.com/client/v4"

class CloudflareAPI:
    def __init__(self, config, profile_name=None):
        self.config = config
        
        if profile_name is None:
            profile_name = config.get("current_profile", "Default")
            
        self.profile_name = profile_name
        prof = config.get("api_profiles", {}).get(profile_name, {})
        
        self.auth_method = prof.get('auth_method', 'token')
        self.api_token = prof.get('api_token', '')
        self.global_api_key = prof.get('global_api_key', '')
        self.email = prof.get('email', '')
        self.timeout = config.get('timeout', 30)
        self.account_id = None

    def get_headers(self):
        headers = {
            "Content-Type": "application/json"
        }
        if self.auth_method == 'token':
            headers["Authorization"] = f"Bearer {self.api_token}"
        else:
            headers["X-Auth-Email"] = self.email
            headers["X-Auth-Key"] = self.global_api_key
        return headers

    def test_connection(self):
        try:
            res = requests.get(f"{BASE_URL}/user/tokens/verify", headers=self.get_headers(), timeout=self.timeout)
            if res.status_code == 200 and res.json().get('success'):
                return True, "Connection successful"
            
            # If not token, try accounts endpoint
            res = requests.get(f"{BASE_URL}/accounts", headers=self.get_headers(), timeout=self.timeout)
            if res.status_code == 200 and res.json().get('success'):
                return True, "Connection successful"
                
            error_msg = self._extract_error(res.json())
            return False, f"Auth failed: {error_msg}"
        except Exception as e:
            return False, str(e)

    def get_account_id(self):
        if self.account_id:
            return self.account_id
            
        try:
            res = requests.get(f"{BASE_URL}/accounts", headers=self.get_headers(), timeout=self.timeout)
            data = res.json()
            if res.status_code == 200 and data.get('success'):
                accounts = data.get('result', [])
                if accounts:
                    self.account_id = accounts[0]['id']
                    return self.account_id
            app_logger.error(f"Failed to get account ID: {self._extract_error(data)}")
            return None
        except Exception as e:
            app_logger.error(f"Exception getting account ID: {e}")
            return None

    def add_zone(self, domain):
        account_id = self.get_account_id()
        if not account_id:
            return False, None, "Could not retrieve Cloudflare Account ID"

        payload = {
            "name": domain,
            "account": {"id": account_id},
            "jump_start": False
        }
        
        try:
            res = requests.post(f"{BASE_URL}/zones", headers=self.get_headers(), json=payload, timeout=self.timeout)
            data = res.json()
            
            if res.status_code == 200 and data.get('success'):
                zone_id = data['result']['id']
                name_servers = data['result'].get('name_servers', [])
                return True, {"zone_id": zone_id, "name_servers": name_servers}, "Success"
            elif res.status_code == 409 or "already exists" in self._extract_error(data).lower():
                # Try to get zone id if it already exists
                return self._get_existing_zone(domain)
            else:
                return False, None, self._extract_error(data)
        except Exception as e:
            return False, None, str(e)

    def _get_existing_zone(self, domain):
        try:
            res = requests.get(f"{BASE_URL}/zones?name={domain}", headers=self.get_headers(), timeout=self.timeout)
            data = res.json()
            if res.status_code == 200 and data.get('success') and len(data['result']) > 0:
                zone = data['result'][0]
                return True, {"zone_id": zone['id'], "name_servers": zone.get('name_servers', [])}, "Zone already exists, retrieved."
            return False, None, "Zone exists but failed to retrieve details."
        except Exception as e:
            return False, None, str(e)

    def get_dns_records(self, zone_id, name=None, record_type=None):
        try:
            url = f"{BASE_URL}/zones/{zone_id}/dns_records"
            params = {}
            if name:
                params['name'] = name
            if record_type:
                params['type'] = record_type
            res = requests.get(url, headers=self.get_headers(), params=params, timeout=self.timeout)
            data = res.json()
            if res.status_code == 200 and data.get('success'):
                return True, data.get('result', []), "Success"
            return False, [], self._extract_error(data)
        except Exception as e:
            return False, [], str(e)

    def update_dns_record(self, zone_id, record_id, record_type, name, content, proxied=True):
        payload = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": 1,
            "proxied": proxied
        }
        try:
            res = requests.put(f"{BASE_URL}/zones/{zone_id}/dns_records/{record_id}", headers=self.get_headers(), json=payload, timeout=self.timeout)
            data = res.json()
            if res.status_code == 200 and data.get('success'):
                return True, "DNS record updated"
            return False, self._extract_error(data)
        except Exception as e:
            return False, str(e)

    def upsert_dns_record(self, zone_id, record_type, name, content, proxied=True):
        success, records, msg = self.get_dns_records(zone_id, name=name, record_type=record_type)
        if success and records:
            errors = []
            for rec in records:
                rec_id = rec['id']
                up_success, up_msg = self.update_dns_record(zone_id, rec_id, record_type, name, content, proxied=proxied)
                if not up_success:
                    errors.append(up_msg)
            if errors:
                return False, " | ".join(errors)
            return True, f"DNS {record_type} updated to {content}"
        
        return self._add_dns_record_post(zone_id, record_type, name, content, proxied=proxied)

    def _add_dns_record_post(self, zone_id, record_type, name, content, proxied=True):
        payload = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": 1, # Automatic
            "proxied": proxied
        }
        
        try:
            res = requests.post(f"{BASE_URL}/zones/{zone_id}/dns_records", headers=self.get_headers(), json=payload, timeout=self.timeout)
            data = res.json()
            if res.status_code == 200 and data.get('success'):
                return True, "DNS added"
            elif "already exists" in self._extract_error(data).lower():
                return True, "DNS already exists"
            else:
                return False, self._extract_error(data)
        except Exception as e:
            return False, str(e)

    def add_dns_record(self, zone_id, record_type, name, content, proxied=True):
        return self.upsert_dns_record(zone_id, record_type, name, content, proxied=proxied)

    def update_domain_ip(self, domain, new_ip):
        if domain.startswith("www."):
            root_domain = domain[4:]
            force_www = True
        else:
            root_domain = domain
            force_www = False

        # 1. Get or create zone
        success, data, msg = self.add_zone(root_domain)
        if not success:
            return False, None, f"Add/Get Zone: {msg}"

        zone_id = data['zone_id']
        ns = data.get('name_servers', [])

        # 2. Update A record for root_domain to new_ip
        success_a, msg_a = self.upsert_dns_record(zone_id, "A", root_domain, new_ip, proxied=True)
        if not success_a:
            return False, ns, f"Update A Record: {msg_a}"

        # 3. Check and update www record if needed
        www_domain = f"www.{root_domain}"
        success_get, www_records, _ = self.get_dns_records(zone_id, name=www_domain)
        if success_get and www_records:
            for rec in www_records:
                if rec.get('type') == 'A':
                    self.update_dns_record(zone_id, rec['id'], "A", www_domain, new_ip, proxied=True)
        elif force_www:
            self.upsert_dns_record(zone_id, "CNAME", www_domain, root_domain, proxied=True)

        # 4. Ensure SSL & Always HTTPS
        self.set_ssl_flexible(zone_id)
        self.set_always_use_https(zone_id)

        return True, ns, f"IP updated to {new_ip}"

    def set_ssl_flexible(self, zone_id):
        payload = {"value": "flexible"}
        try:
            res = requests.patch(f"{BASE_URL}/zones/{zone_id}/settings/ssl", headers=self.get_headers(), json=payload, timeout=self.timeout)
            data = res.json()
            if res.status_code == 200 and data.get('success'):
                return True, "SSL set to Flexible"
            return False, self._extract_error(data)
        except Exception as e:
            return False, str(e)

    def set_always_use_https(self, zone_id):
        payload = {"value": "on"}
        try:
            res = requests.patch(f"{BASE_URL}/zones/{zone_id}/settings/always_use_https", headers=self.get_headers(), json=payload, timeout=self.timeout)
            data = res.json()
            if res.status_code == 200 and data.get('success'):
                return True, "Always Use HTTPS enabled"
            return False, self._extract_error(data)
        except Exception as e:
            return False, str(e)

    def find_zone(self, domain_string):
        """
        Searches Cloudflare for a zone matching domain_string or any of its parent domain candidates.
        Returns (zone_id, zone_name, name_servers) or (None, None, None).
        """
        domain_clean = domain_string.strip().lower()
        if domain_clean.startswith("http://"):
            domain_clean = domain_clean[7:]
        if domain_clean.startswith("https://"):
            domain_clean = domain_clean[8:]
        domain_clean = domain_clean.strip('/')

        parts = domain_clean.split('.')
        if len(parts) < 2:
            return None, None, None

        candidates = []
        for i in range(len(parts) - 1):
            candidate = ".".join(parts[i:])
            candidates.append(candidate)

        for cand in candidates:
            try:
                res = requests.get(f"{BASE_URL}/zones?name={cand}", headers=self.get_headers(), timeout=self.timeout)
                data = res.json()
                if res.status_code == 200 and data.get('success'):
                    results = data.get('result', [])
                    if results:
                        zone = results[0]
                        return zone['id'], zone['name'], zone.get('name_servers', [])
            except Exception as e:
                continue

        return None, None, None

    def get_headers_for_token(self, custom_token=None):
        if custom_token:
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {custom_token}"
            }
        return self.get_headers()

    def get_redirect_ruleset(self, zone_id, custom_token=None):
        headers = self.get_headers_for_token(custom_token)
        try:
            url = f"{BASE_URL}/zones/{zone_id}/rulesets/phases/http_request_dynamic_redirect/entrypoint"
            res = requests.get(url, headers=headers, timeout=self.timeout)
            data = res.json()
            if res.status_code == 200 and data.get('success'):
                return True, data['result'], "Success"
            elif res.status_code == 404:
                # Try fallback GET /zones/{zone_id}/rulesets
                url_fallback = f"{BASE_URL}/zones/{zone_id}/rulesets"
                res_f = requests.get(url_fallback, headers=headers, timeout=self.timeout)
                data_f = res_f.json()
                if res_f.status_code == 200 and data_f.get('success'):
                    for rset in data_f.get('result', []):
                        if rset.get('phase') == 'http_request_dynamic_redirect':
                            # Fetch full ruleset details
                            res_det = requests.get(f"{BASE_URL}/zones/{zone_id}/rulesets/{rset['id']}", headers=headers, timeout=self.timeout)
                            data_det = res_det.json()
                            if res_det.status_code == 200 and data_det.get('success'):
                                return True, data_det['result'], "Success"
                    return True, None, "Ruleset not found"
                return True, None, "Ruleset not found"
            
            err = self._extract_error(data)
            if "10000" in err or "Authentication" in err:
                err = f"Authentication Error (10000): Token CF Anda tidak memiliki izin 'Single Redirect'. Buat Token baru dengan izin Zone -> Single Redirect -> Edit."
            return False, None, err
        except Exception as e:
            return False, None, str(e)

    def fetch_existing_redirect_rules(self, zone_id, custom_token=None):
        """
        Fetches existing rules from Cloudflare and parses them into a list of dicts.
        """
        success, ruleset_data, msg = self.get_redirect_ruleset(zone_id, custom_token=custom_token)
        if not success:
            return False, [], msg

        if not ruleset_data or 'rules' not in ruleset_data:
            return True, [], "No rules found"

        parsed = []
        for r in ruleset_data.get('rules', []):
            desc = r.get('description', '')
            action_params = r.get('action_parameters', {})
            from_val = action_params.get('from_value', {})
            target_url_dict = from_val.get('target_url', {})
            target_url = target_url_dict.get('value', '') if isinstance(target_url_dict, dict) else ''

            parsed.append({
                'id': r.get('id'),
                'description': desc,
                'expression': r.get('expression', ''),
                'target_url': target_url,
                'status_code': from_val.get('status_code', 302),
                'preserve_query_string': from_val.get('preserve_query_string', False)
            })

        return True, parsed, "Success"

    def find_specific_redirect_rule(self, zone_id, target_path, custom_token=None):
        """
        Searches for a specific path rule (e.g. '/jamp' or 'Root') in existing zone rulesets.
        """
        success, rules_list, msg = self.fetch_existing_redirect_rules(zone_id, custom_token=custom_token)
        if not success:
            return False, None, msg

        clean_path = target_path.strip()
        if clean_path.lower() in ['root', '/', '/root']:
            target_key = "Root"
        else:
            if not clean_path.startswith('/'):
                clean_path = '/' + clean_path
            target_key = clean_path

        for r in rules_list:
            desc = r.get('description', '')
            expr = r.get('expression', '')
            if target_key == "Root":
                if desc == "Root" or "wildcard" in expr:
                    return True, r, "Found"
            else:
                clean_k = target_key.lstrip('/')
                if desc == target_key or desc == clean_k or f'"{target_key}"' in expr or f'"{clean_k}"' in expr:
                    return True, r, "Found"

        return True, None, "Rule not found"

    def apply_redirect_rules(self, zone_id, root_url=None, path_rules=None, custom_token=None):
        """
        path_rules: list of dicts [{'path': '/jamp', 'target_url': 'https://...'}]
        root_url: string URL for root rule (if provided)
        """
        headers = self.get_headers_for_token(custom_token)
        
        # 1. Fetch existing ruleset
        success, ruleset_data, msg = self.get_redirect_ruleset(zone_id, custom_token=custom_token)
        if not success:
            return False, f"Get Ruleset Error: {msg}"

        existing_rules = []
        ruleset_id = None
        if ruleset_data:
            ruleset_id = ruleset_data.get('id')
            existing_rules = ruleset_data.get('rules', [])

        # Check if Root rule already exists on Cloudflare
        has_existing_root = any(
            (r.get('description') == "Root" or "wildcard" in r.get('expression', ''))
            for r in existing_rules
        )

        # Build set of target paths to update/replace
        paths_to_update = set()
        # Only update Root if root_url is provided AND root rule does NOT exist yet
        should_add_root = (root_url is not None) and (not has_existing_root)
        
        if root_url is not None and not has_existing_root:
            paths_to_update.add("Root")

        if path_rules:
            for pr in path_rules:
                p = pr['path'].strip()
                if not p.startswith('/'):
                    p = '/' + p
                paths_to_update.add(p)

        def rule_matches_target(rule):
            desc = rule.get('description', '')
            expr = rule.get('expression', '')
            for p in paths_to_update:
                if p == "Root":
                    if desc == "Root" or "wildcard" in expr:
                        return True
                else:
                    clean_p = p.lstrip('/')
                    if desc == p or desc == clean_p or f'"{p}"' in expr or f'"{clean_p}"' in expr:
                        return True
            return False

        # Keep existing rules that are not being replaced/updated
        updated_rules = [r for r in existing_rules if not rule_matches_target(r)]

        # Build Path Rules (placed at First)
        new_path_rules = []
        if path_rules:
            for pr in path_rules:
                p = pr['path'].strip()
                if not p.startswith('/'):
                    p = '/' + p
                target_url = pr['target_url'].strip()
                new_path_rules.append({
                    "action": "redirect",
                    "action_parameters": {
                        "from_value": {
                            "status_code": 302,
                            "target_url": {
                                "value": target_url
                            },
                            "preserve_query_string": True
                        }
                    },
                    "expression": f'(http.request.uri contains "{p}")',
                    "description": p,
                    "enabled": True
                })

        # Build Root Rule (placed at Last ONLY if root rule does not exist yet)
        new_root_rule = None
        if should_add_root:
            new_root_rule = {
                "action": "redirect",
                "action_parameters": {
                    "from_value": {
                        "status_code": 302,
                        "target_url": {
                            "value": root_url
                        },
                        "preserve_query_string": False
                    }
                },
                "expression": '(http.request.uri.query wildcard r"")',
                "description": "Root",
                "enabled": True
            }

        # Combine rules: [new_path_rules] + [updated_rules] + [new_root_rule]
        final_rules = new_path_rules + updated_rules
        if new_root_rule:
            final_rules.append(new_root_rule)

        try:
            if ruleset_id:
                url = f"{BASE_URL}/zones/{zone_id}/rulesets/{ruleset_id}"
                payload = {"rules": final_rules}
                res = requests.put(url, headers=headers, json=payload, timeout=self.timeout)
            else:
                url = f"{BASE_URL}/zones/{zone_id}/rulesets"
                payload = {
                    "name": "default",
                    "kind": "zone",
                    "phase": "http_request_dynamic_redirect",
                    "rules": final_rules
                }
                res = requests.post(url, headers=headers, json=payload, timeout=self.timeout)

            data = res.json()
            if res.status_code == 200 and data.get('success'):
                return True, "Redirect rules updated successfully"
            err_msg = self._extract_error(data)
            if "10000" in err_msg or "Authentication" in err_msg:
                err_msg = f"Authentication Error (10000): Token CF Anda tidak memiliki izin 'Single Redirect'. Buat Token baru dengan izin Zone -> Single Redirect -> Edit."
            return False, err_msg
        except Exception as e:
            return False, str(e)

    def _extract_error(self, data):
        if not data:
            return "Empty response from Cloudflare"
        errors = data.get('errors', [])
        if errors:
            return " | ".join([f"{e.get('code', '')}: {e.get('message', '')}" for e in errors])
        return "Unknown API Error"

def find_zone_across_profiles(config, domain_string):
    """
    Searches across all saved Cloudflare profiles in config for a matching zone.
    Returns (profile_name, api_client, zone_id, zone_name, name_servers, error_msg)
    """
    profiles = config.get("api_profiles", {})
    if not profiles:
        return None, None, None, None, None, "Tidak ada profil Cloudflare API yang tersimpan di aplikasi."

    for prof_name in profiles.keys():
        temp_config = config.copy()
        temp_config["current_profile"] = prof_name
        api = CloudflareAPI(temp_config)
        zone_id, zone_name, name_servers = api.find_zone(domain_string)
        if zone_id:
            return prof_name, api, zone_id, zone_name, name_servers, None

    return None, None, None, None, None, "Domain tidak ditemukan pada profil Cloudflare manapun."
