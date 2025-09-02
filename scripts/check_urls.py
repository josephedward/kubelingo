
import requests
import os

def check_urls(file_path):
    with open(file_path, 'r') as f:
        urls = f.readlines()

    with open(file_path, 'w') as f:
        for url in urls:
            url = url.strip()
            if url.startswith('#'):
                f.write(url + '\n')
                continue
            try:
                response = requests.head(url, allow_redirects=True, timeout=5)
                if response.status_code == 404:
                    print(f"URL returned 404: {url}")
                    f.write(f"# {url}\n")
                else:
                    print(f"URL is reachable: {url}")
                    f.write(url + '\n')
            except requests.exceptions.RequestException as e:
                print(f"Failed to reach URL: {url} - {e}")
                f.write(f"# {url} - Failed to reach\n")

if __name__ == "__main__":
    check_urls(os.path.join(os.path.dirname(__file__), '../data/url_list.md'))
