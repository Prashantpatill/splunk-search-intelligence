My Project
curl "http://localhost:8080/api/searches/recent?only_problematic=true&minutes=60" | python3 -c "
import json, sys, subprocess
data = json.load(sys.stdin)
for search in data.get('searches', [])[:3]:  # Save first 3
    sid = search['search_id']
    print(f'Saving {sid}...')
    subprocess.run(['curl', '-X', 'POST', '-s', f'http://localhost:8080/api/searches/{sid}/analyze-and-save'])
    print('Done!')
"