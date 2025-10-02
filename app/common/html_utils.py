def extract_headings(soup):
    headings = []
    for i in range(1, 7):
        headings.extend(tag.get_text(strip=True) for tag in soup.find_all(f'h{i}'))
    return headings

def extract_list_items(soup):
    return [li.get_text(strip=True) for li in soup.find_all('li')]