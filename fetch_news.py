import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re
from datetime import datetime

# 1. PubMed Search Query (Customize medical topics or clinical guidelines here)
PUBMED_QUERY = "(clinical trial[Publication Type] OR practice guideline[Publication Type]) AND (internal medicine OR infectious diseases OR cardiology OR endocrinology)"
PUBMED_MAX_RESULTS = 4

# 2. Public Health RSS Feeds
RSS_FEEDS = [
    {
        "url": "https://www.who.int/rss-feeds/news-english.xml",
        "tag": "Public Health",
        "source": "World Health Organization"
    }
]

def clean_html(raw_html):
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    text = re.sub(cleanr, '', raw_html)
    return " ".join(text.split())

def fetch_pubmed_articles():
    """Fetches latest peer-reviewed articles & abstracts directly from NCBI PubMed API."""
    articles = []
    headers = {'User-Agent': 'MedBloom-Clinical-Portal/1.0 (https://medbloom2025-ai.github.io/medbloom/)'}

    try:
        # Step A: Search PubMed for the latest article IDs (PMIDs)
        encoded_query = urllib.parse.quote(PUBMED_QUERY)
        search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded_query}&retmax={PUBMED_MAX_RESULTS}&sort=date&retmode=json"
        
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as res:
            search_data = json.loads(res.read().decode('utf-8'))
            pmids = search_data.get("esearchresult", {}).get("idlist", [])

        if not pmids:
            return articles

        # Step B: Fetch full abstracts and journal metadata for those PMIDs
        ids_param = ",".join(pmids)
        fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={ids_param}&retmode=xml"
        
        req_fetch = urllib.request.Request(fetch_url, headers=headers)
        with urllib.request.urlopen(req_fetch, timeout=15) as res:
            xml_data = res.read()
            root = ET.fromstring(xml_data)

            for idx, pubmed_article in enumerate(root.findall('.//PubmedArticle')):
                pmid = pubmed_article.findtext('.//PMID') or ''
                title = pubmed_article.findtext('.//ArticleTitle') or 'PubMed Clinical Study'
                journal = pubmed_article.findtext('.//Journal/Title') or 'PubMed Indexed Journal'
                
                # Extract publication date
                pub_year = pubmed_article.findtext('.//JournalIssue/PubDate/Year') or datetime.utcnow().strftime('%Y')
                pub_month = pubmed_article.findtext('.//JournalIssue/PubDate/Month') or ''
                date_str = f"{pub_month} {pub_year}".strip()

                # Combine structured abstract sections (Background, Methods, Results, Conclusion)
                abstract_parts = []
                for abst in pubmed_article.findall('.//AbstractText'):
                    label = abst.attrib.get('Label')
                    text = "".join(abst.itertext()).strip()
                    if text:
                        if label:
                            abstract_parts.append(f"<p class='mb-2'><strong>{label}:</strong> {text}</p>")
                        else:
                            abstract_parts.append(f"<p class='mb-2'>{text}</p>")

                full_abstract_html = "".join(abstract_parts) if abstract_parts else "<p>Full clinical text available directly on PubMed.</p>"
                plain_abstract = clean_html(full_abstract_html)
                summary = (plain_abstract[:175] + "...") if len(plain_abstract) > 175 else plain_abstract

                pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

                articles.append({
                    "id": f"pubmed-{pmid}",
                    "tag": "Clinical Guidelines",
                    "date": date_str,
                    "readTime": f"PubMed • PMID: {pmid}",
                    "title": clean_html(title),
                    "summary": summary,
                    "fullText": f"""
                        <div class='bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs text-slate-600 mb-4'>
                            <strong>Journal:</strong> {journal.title()} &bull; <strong>PMID:</strong> {pmid}
                        </div>
                        {full_abstract_html}
                        <p class='mt-6 pt-4 border-t border-slate-200'>
                            <a href='{pubmed_url}' target='_blank' rel='noopener' class='inline-flex items-center gap-1 font-bold text-teal-600 underline'>
                                View Full Citation & Mesh Terms on PubMed (NCBI) →
                            </a>
                        </p>
                    """
                })
    except Exception as e:
        print(f"PubMed API error: {e}")

    return articles

def fetch_rss_news():
    """Fetches public health alerts from WHO RSS feed."""
    articles = []
    headers = {'User-Agent': 'Mozilla/5.0 (MedBloom Clinical Portal Bot)'}

    for feed in RSS_FEEDS:
        try:
            req = urllib.request.Request(feed["url"], headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                root = ET.fromstring(response.read())
                items = root.findall('.//item')[:2]  # Top 2 WHO public health alerts

                for idx, item in enumerate(items):
                    title = item.findtext('title') or 'Public Health Update'
                    link = item.findtext('link') or '#'
                    desc = clean_html(item.findtext('description') or '')
                    pub_date = item.findtext('pubDate') or ''
                    short_date = pub_date[:16] if (pub_date and len(pub_date) > 16) else datetime.utcnow().strftime('%b %d, %Y')
                    summary = (desc[:175] + "...") if len(desc) > 175 else desc

                    articles.append({
                        "id": f"who-{idx}",
                        "tag": feed["tag"],
                        "date": short_date,
                        "readTime": feed["source"],
                        "title": title,
                        "summary": summary,
                        "fullText": f"<p class='mb-4'>{desc}</p><p class='mt-4'><a href='{link}' target='_blank' rel='noopener' class='inline-flex items-center gap-1 font-bold text-teal-600 underline'>Read Official Briefing at {feed['source']} →</a></p>"
                    })
        except Exception as e:
            print(f"Skipped {feed['source']}: {e}")

    return articles

if __name__ == "__main__":
    all_articles = fetch_pubmed_articles() + fetch_rss_news()
    if all_articles:
        with open('news.json', 'w', encoding='utf-8') as f:
            json.dump(all_articles, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved {len(all_articles)} articles (PubMed + WHO) to news.json")
