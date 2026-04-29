import streamlit as st
import requests
import validators
from bs4 import BeautifulSoup
import re
import socket
import dns.resolver
import whois
from datetime import datetime

# --- CONFIG ---
PAGESPEED_API_KEY = "AIzaSyD1r7vZU9kJbeU5W3gmz2ZJ1xMdb_RPzsA" 

st.set_page_config(page_title="Digital Audit AI", page_icon="🔍", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .google-logo { font-size: 60px; font-weight: bold; text-align: center; margin-bottom: 10px; line-height: 1.2; }
    .report-card { border: 1px solid #e0e0e0; padding: 20px; border-radius: 10px; background: #fff; margin-bottom: 20px; }
    small { color: #5f6368; }
    .status-label { font-weight: bold; color: #1a73e8; }
    </style>
""", unsafe_allow_html=True)

# --- ANALYSIS ENGINES ---

def check_google_index(url):
    """Checks if the domain is indexed on Google"""
    try:
        domain = url.replace('https://', '').replace('http://', '').split('/')[0]
        search_url = f"https://www.google.com/search?q=site:{domain}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(search_url, headers=headers, timeout=5)
        if "did not match any documents" not in response.text and response.status_code == 200:
            return True
        return False
    except:
        return False

def analyze_mobile_responsiveness(url):
    """Checks for technical mobile responsiveness indicators"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        has_media_queries = "@media" in response.text
        
        score = 0
        checks = []
        
        if viewport:
            score += 50
            checks.append("✅ Viewport Meta Tag found.")
        else:
            checks.append("❌ Missing Viewport Meta Tag.")
            
        if has_media_queries:
            score += 50
            checks.append("✅ CSS Media Queries detected.")
        else:
            checks.append("⚠️ Limited CSS Media Queries found.")
            
        return score, checks
    except:
        return 0, ["Could not analyze responsiveness."]

def check_social_links(url):
    """Checks for social media presence on the website"""
    social_platforms = {
        "Facebook": ["facebook.com", "fb.com"],
        "Instagram": ["instagram.com"],
        "Twitter/X": ["twitter.com", "x.com"],
        "LinkedIn": ["linkedin.com"],
        "YouTube": ["youtube.com"],
        "TikTok": ["tiktok.com"]
    }
    found_links = {}
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [a.get('href', '') for a in soup.find_all('a')]
        
        for platform, patterns in social_platforms.items():
            for link in links:
                if any(p in link.lower() for p in patterns):
                    found_links[platform] = link
                    break
        return found_links
    except:
        return {}

def check_blog_presence(url):
    """Checks for the existence of a blog or news section"""
    blog_keywords = ['blog', 'news', 'articles', 'resources', 'insights']
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a')
        
        for link in links:
            text = link.get_text().lower()
            href = link.get('href', '').lower()
            if any(keyword in text or keyword in href for keyword in blog_keywords):
                full_url = href if href.startswith('http') else url.rstrip('/') + '/' + href.lstrip('/')
                return True, full_url
        return False, None
    except:
        return False, None

def get_real_speed(url):
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={PAGESPEED_API_KEY}"
    try:
        response = requests.get(api_url).json()
        metrics = response['lighthouseResult']['audits']
        score = response['lighthouseResult']['categories']['performance']['score'] * 100
        return {
            "Score": int(score),
            "LCP": metrics['largest-contentful-paint']['displayValue'],
            "TBT": metrics['total-blocking-time']['displayValue'],
            "Speed Index": metrics['speed-index']['displayValue']
        }
    except: return None

def extract_brand_info(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        styles = str(soup.find_all('style'))
        hex_codes = re.findall(r'#[0-9a-fA-F]{6}', styles)
        primary_color = hex_codes[0] if hex_codes else "#4285F4"
        font = "Standard Web Fonts"
        if "font-family" in styles:
            font_match = re.search(r'font-family:\s*([^;]+)', styles)
            if font_match: font = font_match.group(1).split(',')[0].replace("'", "").replace('"', "")
        return {"color": primary_color, "font": font}
    except: return {"color": "#4285F4", "font": "Unknown"}

def analyze_images(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        img_tags = soup.find_all(['img', 'source'])
        modern_formats = ['.webp', '.avif', '.svg']
        optimized_count = 0
        total_found = 0
        for img in img_tags:
            src_text = str(img.get('src', '')) + str(img.get('data-src', '')) + str(img.get('srcset', ''))
            if src_text.strip():
                total_found += 1
                if any(fmt in src_text.lower() for fmt in modern_formats): optimized_count += 1
        score = int((optimized_count / total_found) * 100) if total_found > 0 else 100
        return score, total_found
    except: return 0, 0

def analyze_ux(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        imgs = soup.find_all('img')
        has_alt = len([i for i in imgs if i.get('alt')])
        alt_score = (has_alt / len(imgs)) * 100 if imgs else 100
        is_secure = url.startswith('https')
        has_viewport = 'viewport' in response.text.lower()
        ux_score = int((alt_score + (100 if is_secure else 0) + (100 if has_viewport else 0)) / 3)
        notes = []
        if alt_score < 80: notes.append("Missing image Alt tags.")
        if not is_secure: notes.append("Missing HTTPS encryption.")
        if not has_viewport: notes.append("Mobile viewport not defined.")
        return ux_score, notes
    except: return 0, ["Analysis failed."]

def format_date(d):
    if isinstance(d, list): d = d[0]
    return d.strftime('%Y-%m-%d') if isinstance(d, datetime) else "Data Protected/Private"

def get_hosting_details(url):
    domain = url.replace('https://', '').replace('http://', '').split('/')[0]
    try:
        ip_address = socket.gethostbyname(domain)
    except:
        ip_address = "Could not resolve"
        
    try:
        w = whois.whois(domain)
        expiry = w.expiration_date
        if isinstance(expiry, list): expiry = expiry[0]
        days_left = (expiry - datetime.now()).days if isinstance(expiry, datetime) else "N/A"
        
        return {
            "Domain": domain.upper(),
            "IP": ip_address,
            "Provider": w.registrar or "Unknown Provider",
            "RegisteredOn": format_date(w.creation_date),
            "ExpiresOn": format_date(w.expiration_date),
            "UpdatedOn": format_date(w.updated_date),
            "DaysLeft": days_left,
            "Location": w.country or "Global"
        }
    except:
        return {
            "Domain": domain.upper(),
            "IP": ip_address,
            "Provider": "Privacy Protected",
            "RegisteredOn": "Data Private",
            "ExpiresOn": "Data Private",
            "UpdatedOn": "Data Private",
            "DaysLeft": "N/A",
            "Location": "Unknown"
        }

# --- GUI ---

col1, col2, col3 = st.columns([2, 1, 2])
with col2:
    try: st.image("img/logo.jpg", width=150)
    except: st.error("Logo not found in 'img' folder.")

st.markdown('<div class="google-logo">'
            '<span style="color:#4285F4">D</span><span style="color:#EA4335">i</span><span style="color:#FBBC05">g</span><span style="color:#4285F4">i</span><span style="color:#34A853">t</span><span style="color:#EA4335">a</span><span style="color:#4285F4">l</span> '
            '<span style="color:#34A853">A</span><span style="color:#4285F4">u</span><span style="color:#EA4335">d</span><span style="color:#FBBC05">i</span><span style="color:#4285F4">t</span></div>', unsafe_allow_html=True)

url_input = st.text_input("", placeholder="Enter website URL (e.g., https://www.google.com)")

if st.button("Run Full AI Audit", use_container_width=True):
    if not validators.url(url_input):
        st.error("Please enter a valid URL (include https://)")
    else:
        with st.spinner("Analyzing all digital touchpoints..."):
            is_indexed = check_google_index(url_input)
            mobile_score, mobile_checks = analyze_mobile_responsiveness(url_input)
            social_links = check_social_links(url_input)
            has_blog, blog_url = check_blog_presence(url_input)
            speed = get_real_speed(url_input)
            brand = extract_brand_info(url_input)
            img_score, img_total = analyze_images(url_input)
            ux_score, ux_notes = analyze_ux(url_input)
            host = get_hosting_details(url_input)

            st.divider()
            
            if is_indexed:
                st.success("✅ Google Index: This website is indexed on Google.")
            else:
                st.warning("⚠️ Google Index: This website might not be indexed on Google.")

            r1c1, r1c2 = st.columns(2)
            with r1c1:
                st.subheader("⚡ Performance")
                if speed:
                    st.metric("Score", f"{speed['Score']}/100")
                    st.write(f"<small>LCP: {speed['LCP']} | Index: {speed['Speed Index']}</small>", unsafe_allow_html=True)
                else: st.warning("Speed data unavailable.")

            with r1c2:
                st.subheader("🎨 Branding")
                st.write(f"Font: **{brand['font']}**")
                st.color_picker("Brand Color", brand['color'], disabled=True)

            r2c1, r2c2 = st.columns(2)
            with r2c1:
                st.subheader("🖼️ Media Quality")
                st.metric("Optimization", f"{img_score}%")
                st.progress(img_score / 100)
                st.write(f"<small>Assets Found: {img_total}</small>", unsafe_allow_html=True)

            with r2c2:
                st.subheader("🤝 User Friendly")
                st.metric("UX Score", f"{ux_score}%")
                for n in ux_notes: st.write(f"• <small>{n}</small>", unsafe_allow_html=True)

            st.divider()
            # Mobile Responsiveness Section
            st.subheader("📱 Mobile Responsiveness")
            m_col1, m_col2 = st.columns([1, 2])
            with m_col1:
                st.metric("Mobile Ready", f"{mobile_score}%")
            with m_col2:
                for check in mobile_checks:
                    st.write(f"<small>{check}</small>", unsafe_allow_html=True)

            st.divider()
            # Social Media & Content Section
            sc_col1, sc_col2 = st.columns(2)
            with sc_col1:
                st.subheader("📲 Social Media Presence")
                if social_links:
                    for platform, link in social_links.items():
                        st.write(f"✅ **{platform}:** [Link]({link})")
                else:
                    st.info("No social media links detected.")
            
            with sc_col2:
                st.subheader("✍️ Content & Blogs")
                if has_blog:
                    st.write(f"✅ **Blog/News Section Found**")
                    st.write(f"<small>[View Blog Section]({blog_url})</small>", unsafe_allow_html=True)
                else:
                    st.warning("❌ No Blog/News section detected.")

            st.divider()
            st.subheader("🌐 Domain & Hosting Intelligence")
            h1, h2 = st.columns(2)
            with h1:
                st.write(f"**Domain:** `{host['Domain']}`")
                st.write(f"**Registered On:** {host['RegisteredOn']}")
                st.write(f"**Updated On:** {host['UpdatedOn']}")
                st.write(f"**Expires On:** {host['ExpiresOn']}")
            with h2:
                st.write(f"**Hosting Provider:** {host['Provider']}")
                st.write(f"**IP Address:** `{host['IP']}`")
                if isinstance(host['DaysLeft'], int):
                    c = "red" if host['DaysLeft'] < 30 else "#34A853"
                    st.markdown(f"**Days Until Expiry:** <span style='color:{c}; font-size: 20px; font-weight:bold;'>{host['DaysLeft']}</span>", unsafe_allow_html=True)
                else:
                    st.write(f"**Days Until Expiry:** N/A")
            st.write("🔍 Check www.whois.com")

        st.success("Audit Complete!")

# Footer
st.markdown("---")
st.caption("AI Auditor v1.0 | Powered by Data Science, eBEYONDS")