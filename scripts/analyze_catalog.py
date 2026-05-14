import json
from collections import Counter

# Read and parse (handle control chars)
with open(r'd:\SHL\data\catalog.json', 'r', encoding='utf-8') as f:
    catalog = json.loads(f.read(), strict=False)

print(f"Total products: {len(catalog)}")

# Key categories
keys_set = set()
for p in catalog:
    keys_set.update(p.get('keys', []))
print(f"\nKey categories: {sorted(keys_set)}")

# Job levels
jl = set()
for p in catalog:
    jl.update(p.get('job_levels', []))
print(f"\nJob levels: {sorted(jl)}")

# Products per category
kc = Counter()
for p in catalog:
    for k in p.get('keys', []):
        kc[k] += 1
print("\nProducts per category:")
for k, v in kc.most_common():
    print(f"  {k}: {v}")

# Save cleaned version
with open(r'd:\SHL\data\catalog_clean.json', 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)
print(f"\nSaved clean catalog to d:\\SHL\\data\\catalog_clean.json")
