import struct
import zlib

def create_png_bytes(width, height, color_rgba):
    # Pure Python PNG generator for simple icon
    def make_chunk(chunk_type, data):
        return struct.pack('>I', len(data)) + chunk_type + data + struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)

    # PNG Header
    header = b'\x89PNG\r\n\x1a\n'
    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr = make_chunk(b'IHDR', ihdr_data)
    
    # IDAT (image data with orange/violet gradient background and simple cloud/flash logo)
    raw_data = bytearray()
    r_bg, g_bg, b_bg, a_bg = color_rgba
    
    for y in range(height):
        raw_data.append(0) # Filter type 0
        for x in range(width):
            # Simple radial gradient: Center is orange Cloudflare color #F38020 (243, 128, 32)
            dx = x - width // 2
            dy = y - height // 2
            dist = (dx*dx + dy*dy) ** 0.5
            max_dist = width // 2
            
            if dist < max_dist:
                # Orange gradient inside circle
                factor = 1.0 - (dist / max_dist) * 0.4
                r = int(243 * factor)
                g = int(128 * factor)
                b = int(32 * factor)
                a = 255
            else:
                r, g, b, a = 0, 0, 0, 0 # Transparent outside
                
            raw_data.extend([r, g, b, a])
            
    idat = make_chunk(b'IDAT', zlib.compress(bytes(raw_data)))
    iend = make_chunk(b'IEND', b'')
    
    return header + ihdr + idat + iend

def make_ico(png_data, filename="app_icon.ico"):
    # ICO Header: Reserved(2 bytes), Type=1(2 bytes), ImageCount=1(2 bytes)
    ico_header = struct.pack('<HHH', 0, 1, 1)
    
    # Directory Entry: Width(1), Height(1), Colors(1), Reserved(1), Planes(2), BPP(2), Size(4), Offset(4)
    w = 64
    h = 64
    size = len(png_data)
    offset = 6 + 16
    
    ico_dir = struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, size, offset)
    
    with open(filename, 'wb') as f:
        f.write(ico_header + ico_dir + png_data)
    print(f"Generated {filename} successfully ({size} bytes).")

if __name__ == "__main__":
    png_bytes = create_png_bytes(64, 64, (243, 128, 32, 255))
    make_ico(png_bytes, "app_icon.ico")
