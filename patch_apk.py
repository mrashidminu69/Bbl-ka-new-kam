import UnityPy, os, sys, re, zipfile, json

if len(sys.argv) < 3:
    print("Usage: python patch_apk.py <game.obb> <texts_dir>")
    sys.exit(1)

obb, texts_dir = sys.argv[1], sys.argv[2]

print(f"OBB File: {obb}")
print(f"Texts Dir: {texts_dir}")

if not os.path.exists(obb):
    print(f"ERROR: OBB file not found")
    sys.exit(1)

if not os.path.exists(texts_dir):
    print(f"ERROR: Texts directory not found")
    sys.exit(1)

# Ye 10 files replace hongi
TARGETS = [
    ("4221df6f0f151fd4da6bd0ee35123a9b", "STR", "STR_1.txt"),
    ("a1d3846bf78a02641ba348f297151d28", "HEA", "HEA_1.txt"),
    ("182e001bae56bcb419267264cf896a7d", "HUR", "HUR_1.txt"),
    ("e55a407938058bf4d857737a7afc799e", "REN", "REN_1.txt"),
    ("5c887408a240d4a4d8e082224069f7be", "STA", "STA_1.txt"),
    ("44f1cd3b5ddb7ea4b91222fc5dfa1f50", "SCO", "SCO_1.txt"),
    ("2b644b239c6b4664a901147443afeab1", "SIX", "SIX_1.txt"),
    ("80f3f9fb8e627ad4ea01753dc148d016", "THU", "THU_1.txt"),
    ("301e2e6076b6de344a21203af8dac419", "BBL_Bios", "BBL_Bios_1.txt"),
    ("d21c07ca7e62f4e49937026c09a03fc0", "BBLTeam", "BBLTeam_1.txt"),
]

os.makedirs("out", exist_ok=True)
z = zipfile.ZipFile(obb)
infos = [i for i in z.infolist() if not i.is_dir()]
print(f"Total entries in OBB: {len(infos)}")

def find(base):
    pat = re.compile(r"(^|/)" + re.escape(base) + r"(\.split(\d+))?$")
    res = []
    for i in infos:
        m = pat.search(i.filename)
        if m:
            res.append((int(m.group(3) or 0), i))
    return [i for _, i in sorted(res, key=lambda x: x[0])]

failed = False
success = 0

for base, tname, fname in TARGETS:
    print(f"\n{'='*50}")
    print(f"Processing: {tname} ({fname})")
    
    parts = find(base)
    print(f"  Entries in OBB: {len(parts)}")
    
    if not parts:
        print(f"  ❌ NOT FOUND in OBB")
        failed = True
        continue
    
    sizes = [p.file_size for p in parts]
    buf = bytearray()
    for p in parts:
        buf += z.read(p)
    print(f"  Container size: {len(buf)} bytes")
    
    tmp = "tmp_" + base
    open(tmp, "wb").write(buf)
    
    env, ta, old = None, None, None
    try:
        env = UnityPy.load(tmp)
        for obj in env.objects:
            if obj.type.name == "TextAsset":
                d = obj.read()
                if d.m_Name == tname:
                    raw = d.m_Script
                    old = raw.encode("utf-8", "surrogateescape") if isinstance(raw, str) else bytes(raw)
                    ta = obj
                    break
    except Exception as e:
        print(f"  ❌ UnityPy error: {e}")
    
    if old is None:
        print(f"  ❌ TextAsset '{tname}' not found")
        # Available names print karo
        try:
            if env:
                print(f"  Available TextAssets:")
                for obj in env.objects:
                    if obj.type.name == "TextAsset":
                        print(f"    - {obj.read().m_Name}")
        except:
            pass
        failed = True
        continue
    
    newp = os.path.join(texts_dir, fname)
    if not os.path.exists(newp):
        print(f"  ❌ Missing file: {newp}")
        failed = True
        continue
    
    new = open(newp, "rb").read()
    if new.startswith(b"\xef\xbb\xbf") and not old.startswith(b"\xef\xbb\xbf"):
        new = new[3:]
    
    try:
        json.loads(new.decode("utf-8"))
    except Exception as e:
        print(f"  ❌ Not valid JSON: {e}")
        failed = True
        continue
    
    chunks = None
    off = buf.find(old)
    
    if off >= 0 and buf.find(old, off + 1) < 0:
        # In-place patch
        if len(new) > len(old):
            new = json.dumps(json.loads(new.decode("utf-8")), ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
        if len(new) > len(old):
            print(f"  ❌ NEW TEXT TOO LONG: {len(new)} > {len(old)}")
            failed = True
            continue
        used = len(new)
        new = new + b" " * (len(old) - len(new))
        buf[off:off + len(old)] = new
        pos, chunks = 0, {}
        for p, sz in zip(parts, sizes):
            chunks[p.filename] = bytes(buf[pos:pos + sz])
            pos += sz
        print(f"  ✅ Patched in place (old: {len(old)}, new: {used})")
    
    elif len(parts) == 1:
        # UnityPy re-save
        try:
            tree = ta.read_typetree()
            tree["m_Script"] = new.decode("utf-8")
            ta.save_typetree(tree)
            chunks = {parts[0].filename: env.file.save()}
            print(f"  ✅ Re-saved with UnityPy")
        except Exception as e:
            print(f"  ❌ Re-save failed: {e}")
            failed = True
            continue
    else:
        print(f"  ❌ Cannot patch: text not found as plain bytes")
        failed = True
        continue
    
    # Sirf wahi 10 files out/ mein save karo
    for name, data in chunks.items():
        outpath = os.path.join("out", os.path.basename(name))
        open(outpath, "wb").write(data)
        print(f"  📝 Saved: {os.path.basename(name)}")
        success += 1

print(f"\n{'='*50}")
print(f"RESULT: {success}/{len(TARGETS)} files patched")
if failed:
    print("⚠️  Some files failed. Check errors above.")
    sys.exit(1)
else:
    print("🎉 All 10 files patched successfully!")
