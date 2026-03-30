# original script by @Kuramamod
# decode by @bang_albin

import requests
import time
import base64
import re
import logging
import os
import json
from datetime import datetime
from urllib.parse import urlparse
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.style import Style
from rich.text import Text
from rich import print as rprint
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Dict, List, Optional, Union
import random
import shutil

console = Console(width=shutil.get_terminal_size().columns)

NAME = "Anime Lovers V3"
VERSION = "2.1"

CHANGELOG = [
    {
        "version": "2.1",
        "date": "2025-05-29",
        "changes": [
            "Added VIP Checker Bulk feature for checking multiple accounts",
            "Added Permanent VIP option",
            "Implemented account validation before processing",
            "Added custom theme support with color customization",
            "Improved UI responsiveness for different terminal sizes"
        ]
    },
    {
        "version": "2.0",
        "date": "2025-03-28",
        "changes": [
            "Added comprehensive changelog feature",
            "Enhanced proxy configuration with authentication support",
            "Added Telegram notification system",
            "Improved batch processing with configurable delays",
            "Added UI theme customization (dark/light mode)"
        ]
    },
    {
        "version": "1.5",
        "date": "2023-03-27",
        "changes": [
            "Added email batch processing from .txt files",
            "Implemented performance optimization settings",
            "Added VIP preset configurations",
            "Enhanced security settings"
        ]
    },
    {
        "version": "1.0",
        "date": "2025-03-26",
        "changes": [
            "Initial release of Anime Lovers V3",
            "Complete rewrite with Rich UI",
            "Multi-threading support",
            "Basic VIP management features"
        ]
    }
]

DEFAULT_SETTINGS = {
    'basic': {
        'max_workers': 5,
        'timeout': 30,
        'retry_attempts': 3,
        'api_version': 'v1.1.9',
        'user_agent': 'Dart/3.1 (dart:io)'
    },
    'proxy': {
        'enabled': False,
        'url': 'http://139.59.1.14:3128',
        'auth': None
    },
    'endpoints': {
        'login': 'https://apps.animekita.org/api/v1.1.9/model/login.php',
        'vip': 'https://apps.animekita.org/api/v1.1.9/model/vip.php',
        'config': 'https://apps.animekita.org/api/v1.1.9/model/app-config.php'
    },
    'notifications': {
        'email': '',
        'telegram': {
            'enabled': False,
            'bot_token': '',
            'chat_id': ''
        },
        'success_only': True
    },
    'performance': {
        'batch_size': 50,
        'delay_between_batches': 2,
        'throttle_requests': True
    },
    'vip_presets': {
        'default_level': '3',
        'default_duration': '12',
        'custom_user_id': '39720843761',
        'permanent_vip': True
    },
    'ui': {
        'theme': 'dark',
        'show_animations': True,
        'language': 'id',
        'show_changelog_on_startup': True,
        'custom_theme': {
            'primary_color': 'magenta',
            'success_color': 'green',
            'error_color': 'red',
            'info_color': 'cyan'
        }
    },
    'security': {
        'encrypt_logs': False,
        'clear_cache_on_exit': True,
        'verify_ssl': True
    }
}

current_settings = DEFAULT_SETTINGS.copy()

headers = {
    'Host': 'apps.animekita.org',
    'User-Agent': current_settings['basic']['user_agent'],
    'Content-Type': 'text/plain; charset=utf-8',
    'Accept': 'application/json',
    'Accept-Encoding': 'gzip',
    'Access-Control-Allow-Origin': '*'
}

logging.basicConfig(
    filename='anime_lovers.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Auto-save thread
autosave_thread = None
autosave_running = False

def log_activity(message: str) -> None:
    """Log activity with optional encryption"""
    if current_settings['security']['encrypt_logs']:
        message = f"ENC:{base64.b64encode(message.encode()).decode()}"
    logging.info(message)

def validate_email(email: str) -> bool:
    """Validate email format with regex"""
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(regex, email):
        return True
    console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Format email tidak valid: {email}[/]")
    return False

def validate_account(email: str) -> bool:
    """Validate account by attempting login"""
    url = current_settings['endpoints']['login']
    payload = f'{{"user":"{NAME}","email":"{email}"}}'
    proxies = get_proxy_config()
    
    try:
        response = requests.post(
            url,
            headers=headers,
            data=payload,
            timeout=current_settings['basic']['timeout'],
            proxies=proxies,
            verify=current_settings['security']['verify_ssl']
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Akun tidak valid: {email}[/]")
        return False

def validate_proxy_url(url: str) -> bool:
    """Validate proxy URL format"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_proxy_config() -> Optional[Dict]:
    """Return formatted proxy configuration"""
    if not current_settings['proxy']['enabled']:
        return None
    
    proxies = {
        'http': current_settings['proxy']['url'],
        'https': current_settings['proxy']['url']
    }
    
    if current_settings['proxy']['auth']:
        proxies['auth'] = current_settings['proxy']['auth']
    
    return proxies

def vip_date(epoch_time: int) -> str:
    """Convert epoch time to readable date"""
    if epoch_time == 0:
        return "-"
    return datetime.fromtimestamp(epoch_time).strftime('%Y-%m-%d %H:%M:%S')

def show_current_time() -> None:
    """Display current time"""
    console.print(f"[{current_settings['ui']['custom_theme']['info_color']}]⌚ Waktu Sistem: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]")

def login(email: str) -> Optional[str]:
    """Login to the Anime Lovers system with retry mechanism"""
    url = current_settings['endpoints']['login']
    payload = f'{{"user":"{NAME}","email":"{email}"}}'
    proxies = get_proxy_config()
    
    for attempt in range(current_settings['basic']['retry_attempts']):
        try:
            with console.status(f"[{current_settings['ui']['custom_theme']['info_color']}]Sedang melakukan login...[/]", spinner="dots"):
                response = requests.post(
                    url,
                    headers=headers,
                    data=payload,
                    timeout=current_settings['basic']['timeout'],
                    proxies=proxies,
                    verify=current_settings['security']['verify_ssl']
                )
                response.raise_for_status()
                data = response.json()['data'][0]
                
                console.print(Panel.fit(
                    f"[{current_settings['ui']['custom_theme']['success_color']}]✓ Login Berhasil[/]\n"
                    f"[bold]Email:[/] {email}\n"
                    f"[bold]Nama:[/] {data['user']}\n"
                    f"[bold]Token:[/] {data['token'][:15]}...",
                    title="Login Status",
                    border_style=current_settings['ui']['custom_theme']['success_color']
                ))
                
                log_activity(f"User {email} logged in successfully.")
                return data['token']
                
        except requests.exceptions.RequestException as e:
            if attempt < current_settings['basic']['retry_attempts'] - 1:
                console.print(f"[yellow]⌛ Attempt {attempt + 1} failed, retrying...[/yellow]")
                time.sleep(2)
            else:
                console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Gagal terhubung ke server untuk email {email}: {e}[/]")
                return None

def get_data(token: str, email: str) -> Dict:
    """Get user data from the API"""
    payload = {"token": token}
    url = current_settings['endpoints']['config']
    proxies = get_proxy_config()
    
    try:
        with console.status(f"[{current_settings['ui']['custom_theme']['info_color']}]Mengambil data untuk {email}...[/]", spinner="dots"):
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=current_settings['basic']['timeout'],
                proxies=proxies,
                verify=current_settings['security']['verify_ssl']
            )
            response.raise_for_status()
            data = response.json()["data"][0]
            
            table = Table(show_header=True, header_style="bold " + current_settings['ui']['custom_theme']['primary_color'])
            table.add_column("Attribute", style=current_settings['ui']['custom_theme']['info_color'])
            table.add_column("Value", style=current_settings['ui']['custom_theme']['success_color'])
            
            table.add_row("Email", email)
            table.add_row("Level", str(data['level']))
            table.add_row("Rank", str(data['rank']))
            table.add_row("VIP Level", str(data['vipLevel']))
            table.add_row("VIP Expiry", vip_date(data['vipExp']))
            
            console.print(Panel.fit(
                table,
                title=f"User Data - {email}",
                border_style=current_settings['ui']['custom_theme']['primary_color']
            ))
            
            return data
            
    except requests.exceptions.RequestException as e:
        console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Gagal mengambil data untuk {email}: {e}[/]")
        return {}

def set_premium(token: str, encoded_token: str, email: str) -> Optional[int]:
    """Set premium status for the user"""
    payload = {"token": token, "vip": encoded_token + "%3D%3D"}
    url = current_settings['endpoints']['vip']
    proxies = get_proxy_config()
    
    try:
        response = requests.post(
            url,
            headers=headers,
            data=payload,
            timeout=current_settings['basic']['timeout'],
            proxies=proxies,
            verify=current_settings['security']['verify_ssl']
        )
        response.raise_for_status()
        send_notification(f"VIP set successfully for {email}")
        return response.status_code
    except requests.exceptions.RequestException as e:
        console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Gagal mengatur premium untuk {email}: {e}[/]")
        send_notification(f"Failed to set VIP for {email}: {str(e)}", is_error=True)
        return None

def encode_token(is_permanent: bool = False) -> Optional[str]:
    """Generate and encode VIP token"""
    user_id = current_settings['vip_presets']['custom_user_id']
    
    vip_level = Prompt.ask(
        "Pilih Level VIP",
        choices=["1", "2", "3"],
        default=current_settings['vip_presets']['default_level']
    )
    
    if is_permanent:
        vip_exp = "999"
    else:
        vip_exp = Prompt.ask(
            "Pilih Masa VIP (dalam bulan)",
            choices=["1", "3", "6", "9", "12", "custom"],
            default=current_settings['vip_presets']['default_duration']
        )
        
        if vip_exp == "custom":
            vip_exp = IntPrompt.ask("Masukkan jumlah bulan (angka)")
    
    token_data = f"{user_id}_{vip_level}_{vip_exp}"
    encoded_token = base64.b64encode(token_data.encode('utf-8')).decode('utf-8')
    
    console.print(f"[{current_settings['ui']['custom_theme']['success_color']}]✓ Token VIP berhasil dibuat[/]")
    return encoded_token

def check_vip_bulk(emails: List[str]) -> None:
    """Check VIP status for multiple accounts"""
    console.print(Panel.fit(
        "[bold]VIP CHECKER BULK[/bold]",
        border_style=current_settings['ui']['custom_theme']['primary_color']
    ))
    
    results = []
    with ThreadPoolExecutor(max_workers=current_settings['basic']['max_workers']) as executor:
        futures = [executor.submit(lambda e: (e, login(e)), email) for email in emails]
        for future in as_completed(futures):
            email, token = future.result()
            if token:
                data = get_data(token, email)
                results.append({
                    'email': email,
                    'vip_level': data.get('vipLevel', 'N/A'),
                    'vip_expiry': vip_date(data.get('vipExp', 0))
                })
    
    table = Table(show_header=True, header_style="bold " + current_settings['ui']['custom_theme']['primary_color'])
    table.add_column("Email", style=current_settings['ui']['custom_theme']['info_color'])
    table.add_column("VIP Level", style=current_settings['ui']['custom_theme']['success_color'])
    table.add_column("VIP Expiry", style=current_settings['ui']['custom_theme']['success_color'])
    
    for result in results:
        table.add_row(result['email'], str(result['vip_level']), result['vip_expiry'])
    
    console.print(Panel.fit(
        table,
        title="VIP Status Results",
        border_style=current_settings['ui']['custom_theme']['primary_color']
    ))

def show_loading(email_count: int) -> None:
    """Show animated loading progress"""
    if not current_settings['ui']['show_animations']:
        console.print(f"[{current_settings['ui']['custom_theme']['info_color']}]Memproses {email_count} akun...[/]")
        return
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=min(shutil.get_terminal_size().columns // 2, 50)),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        task = progress.add_task(f"[{current_settings['ui']['custom_theme']['info_color']}]Memproses {email_count} akun...", total=100)
        for _ in range(100):
            progress.update(task, advance=1)
            time.sleep(0.02)
    
    console.print(f"[{current_settings['ui']['custom_theme']['success_color']}]✓ Proses selesai![/]")

def process_email(email: str, encoded_token: Optional[str] = None, is_extend: bool = False, is_permanent: bool = False) -> bool:
    """Process a single email account"""
    try:
        
        if not validate_account(email):
            return False
        
        token = login(email)
        if not token:
            return False
        
        console.print(Panel.fit(
            f"[bold]Data Sebelum {'Perpanjangan' if is_extend else 'Upgrade'}{' Permanen' if is_permanent else ''}[/bold]",
            border_style=current_settings['ui']['custom_theme']['primary_color']
        ))
        get_data(token, email)
        
        if encoded_token is None:
            encoded_token = encode_token(is_permanent)
            if encoded_token is None:
                console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Proses dibatalkan. Input tidak valid.[/]")
                return False
        
        set_premium(token, encoded_token, email)
        
        console.print(Panel.fit(
            f"[bold]Data Setelah {'Perpanjangan' if is_extend else 'Upgrade'}{' Permanen' if is_permanent else ''}[/bold]",
            border_style=current_settings['ui']['custom_theme']['primary_color']
        ))
        get_data(token, email)
        
        return True
    except Exception as e:
        console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Error processing {email}: {str(e)}[/]")
        send_notification(f"Error processing {email}: {str(e)}", is_error=True)
        return False

def process_batch(emails: List[str], is_extend: bool = False, is_permanent: bool = False) -> int:
    """Process emails in batches with delay"""
    success_count = 0
    batch_size = current_settings['performance']['batch_size']
    
    for i in range(0, len(emails), batch_size):
        batch = emails[i:i + batch_size]
        
        with ThreadPoolExecutor(max_workers=current_settings['basic']['max_workers']) as executor:
            futures = [executor.submit(process_email, email, None, is_extend, is_permanent) for email in batch]
            for future in as_completed(futures):
                if future.result():
                    success_count += 1
       
        if (i + batch_size < len(emails)) and current_settings['performance']['throttle_requests']:
            delay = current_settings['performance']['delay_between_batches']
            console.print(f"[yellow]⏳ Menunggu {delay} detik sebelum batch berikutnya...[/yellow]")
            time.sleep(delay)
    
    return success_count

def process_multiple_emails(emails: List[str], is_extend: bool = False, is_permanent: bool = False) -> None:
    """Process multiple emails with threading"""
    encoded_token = None
    if not is_extend:
        encoded_token = encode_token(is_permanent)
        if encoded_token is None:
            console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Proses dibatalkan. Input tidak valid.[/]")
            return
    
    show_loading(len(emails))
    
    if current_settings['performance']['batch_size'] > 0 and len(emails) > current_settings['performance']['batch_size']:
        success_count = process_batch(emails, is_extend, is_permanent)
    else:
        success_count = 0
        with ThreadPoolExecutor(max_workers=current_settings['basic']['max_workers']) as executor:
            futures = []
            for email in emails:
                futures.append(executor.submit(process_email, email, encoded_token, is_extend, is_permanent))
            
            for future in as_completed(futures):
                if future.result():
                    success_count += 1
    
    console.print(Panel.fit(
        f"[{current_settings['ui']['custom_theme']['success_color']}]✓ Proses selesai! {success_count}/{len(emails)} akun berhasil diproses.[/]",
        border_style=current_settings['ui']['custom_theme']['success_color']
    ))
    show_current_time()

def send_notification(message: str, is_error: bool = False) -> None:
    """Send notification based on settings"""
    if is_error and current_settings['notifications']['success_only']:
        return
    
    if current_settings['notifications']['email']:
        pass
        
    if current_settings['notifications']['telegram']['enabled']:
        send_telegram_notification(message)

def send_telegram_notification(message: str) -> None:
    """Send Telegram notification"""
    bot_token = current_settings['notifications']['telegram']['bot_token']
    chat_id = current_settings['notifications']['telegram']['chat_id']
    
    if not bot_token or not chat_id:
        return
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': f"{NAME} {VERSION} Notification:\n{message}",
            'parse_mode': 'HTML'
        }
        
        requests.post(
            url,
            json=payload,
            timeout=current_settings['basic']['timeout'],
            verify=current_settings['security']['verify_ssl']
        )
    except Exception as e:
        console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Gagal mengirim notifikasi Telegram: {e}[/]")

def configure_basic_settings() -> None:
    """Configure basic application settings"""
    current_settings['basic']['max_workers'] = IntPrompt.ask(
        "Jumlah maksimal workers (thread)",
        default=current_settings['basic']['max_workers']
    )
    
    current_settings['basic']['timeout'] = IntPrompt.ask(
        "Timeout koneksi (detik)",
        default=current_settings['basic']['timeout']
    )
    
    current_settings['basic']['retry_attempts'] = IntPrompt.ask(
        "Jumlah percobaan ulang",
        default=current_settings['basic']['retry_attempts']
    )
    
    current_settings['basic']['api_version'] = Prompt.ask(
        "Versi API",
        default=current_settings['basic']['api_version']
    )
    
    headers['User-Agent'] = current_settings['basic']['user_agent']

def configure_proxy() -> None:
    """Configure proxy settings"""
    current_settings['proxy']['enabled'] = Confirm.ask(
        "Aktifkan proxy?",
        default=current_settings['proxy']['enabled']
    )
    
    if current_settings['proxy']['enabled']:
        current_settings['proxy']['url'] = Prompt.ask(
            "Proxy URL (contoh: http://127.0.0.1:8080)",
            default=current_settings['proxy']['url']
        )
        
        if not validate_proxy_url(current_settings['proxy']['url']):
            console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Format proxy URL tidak valid[/]")
            current_settings['proxy']['enabled'] = False
            return
        
        if Confirm.ask("Proxy butuh autentikasi?"):
            current_settings['proxy']['auth'] = Prompt.ask(
                "Autentikasi proxy (user:pass)",
                default=current_settings['proxy']['auth'] or ''
            )

def configure_endpoints() -> None:
    """Configure API endpoints"""
    table = Table(title="Current Endpoints")
    table.add_column("Service", style=current_settings['ui']['custom_theme']['info_color'])
    table.add_column("URL", style=current_settings['ui']['custom_theme']['success_color'])
    
    for service, url in current_settings['endpoints'].items():
        table.add_row(service, url)
    
    console.print(table)
    
    service = Prompt.ask(
        "Pilih endpoint yang ingin diubah (login/vip/config)",
        choices=["login", "vip", "config"],
        default="login"
    )
    
    new_url = Prompt.ask(
        f"Masukkan URL baru untuk {service}",
        default=current_settings['endpoints'][service]
    )
    
    current_settings['endpoints'][service] = new_url

def configure_notifications() -> None:
    """Configure notification settings"""
    current_settings['notifications']['email'] = Prompt.ask(
        "Email notifikasi (kosongkan untuk disable)",
        default=current_settings['notifications']['email'] or ''
    )
    
    current_settings['notifications']['telegram']['enabled'] = Confirm.ask(
        "Aktifkan notifikasi Telegram?",
        default=current_settings['notifications']['telegram']['enabled']
    )
    
    if current_settings['notifications']['telegram']['enabled']:
        current_settings['notifications']['telegram']['bot_token'] = Prompt.ask(
            "Token bot Telegram",
            default=current_settings['notifications']['telegram']['bot_token'] or ''
        )
        
        current_settings['notifications']['telegram']['chat_id'] = Prompt.ask(
            "Chat ID Telegram",
            default=current_settings['notifications']['telegram']['chat_id'] or ''
        )
    
    current_settings['notifications']['success_only'] = Confirm.ask(
        "Hanya kirim notifikasi untuk sukses?",
        default=current_settings['notifications']['success_only']
    )

def configure_performance() -> None:
    """Configure performance settings"""
    current_settings['performance']['batch_size'] = IntPrompt.ask(
        "Ukuran batch (jumlah email per proses)",
        default=current_settings['performance']['batch_size']
    )
    
    current_settings['performance']['delay_between_batches'] = IntPrompt.ask(
        "Delay antar batch (detik)",
        default=current_settings['performance']['delay_between_batches']
    )
    
    current_settings['performance']['throttle_requests'] = Confirm.ask(
        "Aktifkan throttle requests?",
        default=current_settings['performance']['throttle_requests']
    )

def configure_vip_presets() -> None:
    """Configure VIP preset settings"""
    current_settings['vip_presets']['default_level'] = Prompt.ask(
        "Default VIP Level",
        choices=["1", "2", "3"],
        default=current_settings['vip_presets']['default_level']
    )
    
    current_settings['vip_presets']['default_duration'] = Prompt.ask(
        "Default durasi VIP (bulan)",
        choices=["1", "3", "6", "9", "12"],
        default=current_settings['vip_presets']['default_duration']
    )
    
    current_settings['vip_presets']['custom_user_id'] = Prompt.ask(
        "Custom User ID",
        default=current_settings['vip_presets']['custom_user_id']
    )
    
    current_settings['vip_presets']['permanent_vip'] = Confirm.ask(
        "Aktifkan VIP permanen secara default?",
        default=current_settings['vip_presets']['permanent_vip']
    )

def configure_ui() -> None:
    """Configure UI settings with custom theme"""
    current_settings['ui']['theme'] = Prompt.ask(
        "Pilih tema antarmuka",
        choices=["dark", "light"],
        default=current_settings['ui']['theme']
    )
    
    current_settings['ui']['show_animations'] = Confirm.ask(
        "Tampilkan animasi?",
        default=current_settings['ui']['show_animations']
    )
    
    current_settings['ui']['language'] = Prompt.ask(
        "Bahasa antarmuka",
        choices=["id", "en"],
        default=current_settings['ui']['language']
    )
    
    current_settings['ui']['show_changelog_on_startup'] = Confirm.ask(
        "Tampilkan changelog saat startup?",
        default=current_settings['ui']['show_changelog_on_startup']
    )
   
    console.print(Panel.fit(
        "[bold]KUSTOMISASI TEMA[/bold]",
        border_style=current_settings['ui']['custom_theme']['primary_color']
    ))
    
    color_choices = ["red", "green", "blue", "cyan", "magenta", "yellow", "white"]
    
    current_settings['ui']['custom_theme']['primary_color'] = Prompt.ask(
        "Warna utama (panel, judul)",
        choices=color_choices,
        default=current_settings['ui']['custom_theme']['primary_color']
    )
    
    current_settings['ui']['custom_theme']['success_color'] = Prompt.ask(
        "Warna sukses (pesan sukses)",
        choices=color_choices,
        default=current_settings['ui']['custom_theme']['success_color']
    )
    
    current_settings['ui']['custom_theme']['error_color'] = Prompt.ask(
        "Warna error (pesan gagal)",
        choices=color_choices,
        default=current_settings['ui']['custom_theme']['error_color']
    )
    
    current_settings['ui']['custom_theme']['info_color'] = Prompt.ask(
        "Warna info (pesan informasi)",
        choices=color_choices,
        default=current_settings['ui']['custom_theme']['info_color']
    )

def configure_security() -> None:
    """Configure security settings"""
    current_settings['security']['encrypt_logs'] = Confirm.ask(
        "Enkripsi file log?",
        default=current_settings['security']['encrypt_logs']
    )
    
    current_settings['security']['clear_cache_on_exit'] = Confirm.ask(
        "Bersihkan cache saat keluar?",
        default=current_settings['security']['clear_cache_on_exit']
    )
    
    current_settings['security']['verify_ssl'] = Confirm.ask(
        "Verifikasi sertifikat SSL?",
        default=current_settings['security']['verify_ssl']
    )

def save_settings_to_file() -> None:
    """Save current settings to file"""
    try:
        with open('anime_lovers_settings.json', 'w') as f:
            json.dump(current_settings, f, indent=4)
        console.print(f"[{current_settings['ui']['custom_theme']['success_color']}]✓ Pengaturan berhasil disimpan[/]")
    except Exception as e:
        console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Gagal menyimpan pengaturan: {str(e)}[/]")

def load_settings_from_file() -> None:
    """Load settings from file"""
    try:
        if os.path.exists('anime_lovers_settings.json'):
            with open('anime_lovers_settings.json', 'r') as f:
                loaded_settings = json.load(f)
                current_settings.update(loaded_settings)
            console.print(f"[{current_settings['ui']['custom_theme']['success_color']}]✓ Pengaturan berhasil dimuat[/]")
    except Exception as e:
        console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Gagal memuat pengaturan: {str(e)}[/]")

def display_changelog() -> None:
    """Display application changelog"""
    console.print(Panel.fit(
        f"[bold]CHANGELOG - Anime Lovers V3[/bold]\n"
        f"Versi Terkini: [{current_settings['ui']['custom_theme']['success_color']}]{VERSION}[/]",
        border_style=current_settings['ui']['custom_theme']['primary_color']
    ))
    
    for entry in CHANGELOG:
        console.print(Panel.fit(
            f"[bold]Versi {entry['version']}[/bold] - {entry['date']}",
            border_style=current_settings['ui']['custom_theme']['success_color'] if entry['version'] == VERSION else current_settings['ui']['custom_theme']['primary_color']
        ))
        
        changes_table = Table.grid(padding=(0, 2))
        changes_table.add_column("•", style=current_settings['ui']['custom_theme']['info_color'])
        changes_table.add_column("Deskripsi", style="white")
        
        for change in entry['changes']:
            changes_table.add_row("•", change)
        
        console.print(changes_table)
        console.print() 

def start_autosave() -> None:
    """Start background autosave thread"""
    global autosave_thread, autosave_running
    
    if autosave_thread is None or not autosave_thread.is_alive():
        autosave_running = True
        autosave_thread = threading.Thread(target=autosave_worker, daemon=True)
        autosave_thread.start()

def stop_autosave() -> None:
    """Stop autosave thread"""
    global autosave_running
    autosave_running = False

def autosave_worker() -> None:
    """Background worker for autosaving settings"""
    while autosave_running:
        time.sleep(300)
        save_settings_to_file()

def display_welcome() -> None:
    """Display welcome banner with responsive width"""
    theme_style = Style(bgcolor="black") if current_settings['ui']['theme'] == 'dark' else Style(bgcolor="white")
    
    banner = Text(f"""
                  𝗦𝗰𝗿𝗶𝗽𝘁 𝗔𝗻𝗶𝗺𝗲𝗟𝗼𝘃𝗲𝗿𝘀 𝗩𝟯 
 
何か失ってもまた見つけることはできるけど、捨てたものは二度と戻らない
"𝘑𝘪𝘬𝘢 𝘬𝘢𝘮𝘶 𝘬𝘦𝘩𝘪𝘭𝘢𝘯𝘨𝘢𝘯 𝘴𝘦𝘴𝘶𝘢𝘵𝘶, 𝘬𝘢𝘮𝘶 𝘥𝘢𝘱𝘢𝘵 𝘮𝘦𝘯𝘦𝘮𝘶𝘬𝘢𝘯𝘯𝘺𝘢 𝘬𝘦𝘮𝘣𝘢𝘭𝘪, 𝘵𝘦𝘵𝘢𝘱𝘪 𝘬𝘢𝘮𝘶 𝘵𝘪𝘥𝘢𝘬 𝘢𝘬𝘢𝘯 𝘱𝘦𝘳𝘯𝘢𝘩 𝘮𝘦𝘯𝘨𝘦𝘮𝘣𝘢𝘭𝘪𝘬𝘢𝘯 𝘢𝘱𝘢 𝘺𝘢𝘯𝘨 𝘬𝘢𝘮𝘶 𝘣𝘶𝘢𝘯𝘨." """, 
    style="bold " + current_settings['ui']['custom_theme']['primary_color'])
    
    console.print(Panel.fit(
        banner,
        subtitle=f"Otaku Indonesia",
        border_style=current_settings['ui']['custom_theme']['error_color'],
        style=theme_style,
        width=min(shutil.get_terminal_size().columns, 100)
    ))
    
    console.print(Panel.fit(
        f"[yellow]⚠ Gunakan tool ini dengan bijak. Bertanggung jawablah atas semua tindakan Anda.[/yellow]",
        border_style="yellow",
        style=theme_style,
        width=min(shutil.get_terminal_size().columns, 100)
    ))
    
    if current_settings['ui']['show_changelog_on_startup']:
        if Confirm.ask(f"\n[{current_settings['ui']['custom_theme']['info_color']}]Tampilkan changelog terbaru?[/]", default=True):
            display_changelog()
            input("\nTekan Enter untuk melanjutkan...")

def show_settings_menu() -> None:
    """Display settings menu"""
    while True:
        console.print(Panel.fit(
            "[bold]PENGATURAN APLIKASI[/bold]",
            border_style=current_settings['ui']['custom_theme']['primary_color'],
            width=min(shutil.get_terminal_size().columns, 80)
        ))
        
        options = Table.grid(padding=(1, 2))
        options.add_column("Menu", style=current_settings['ui']['custom_theme']['info_color'])
        options.add_column("Deskripsi", style="white")
        
        options.add_row("1", "⚙️  Pengaturan Dasar")
        options.add_row("2", "🔌  Pengaturan Proxy")
        options.add_row("3", "🌐  Endpoint API")
        options.add_row("4", "🔔  Notifikasi")
        options.add_row("5", "🚀  Performa")
        options.add_row("6", "👑  Preset VIP")
        options.add_row("7", "🎨  Tampilan UI")
        options.add_row("8", "🔒  Keamanan")
        options.add_row("9", "📜  Tampilkan Changelog")
        options.add_row("0", "🔙  Kembali ke Menu Utama")
        
        console.print(options)
        
        choice = Prompt.ask("Pilih menu pengaturan", choices=[str(i) for i in range(10)])
        
        if choice == '1': configure_basic_settings()
        elif choice == '2': configure_proxy()
        elif choice == '3': configure_endpoints()
        elif choice == '4': configure_notifications()
        elif choice == '5': configure_performance()
        elif choice == '6': configure_vip_presets()
        elif choice == '7': configure_ui()
        elif choice == '8': configure_security()
        elif choice == '9': display_changelog()
        elif choice == '0': return

def load_emails_from_file(file_path: str) -> Optional[List[str]]:
    """Load emails from a text file"""
    try:
        with open(file_path, 'r') as file:
            emails = [line.strip() for line in file if line.strip()]
        return emails
    except FileNotFoundError:
        console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ File tidak ditemukan: {file_path}[/]")
        return None
    except Exception as e:
        console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Gagal membaca file: {str(e)}[/]")
        return None

def main() -> None:
    """Main program function"""
  
    load_settings_from_file()
    start_autosave()
    display_welcome()
    
    valid_emails = []
    
    while True:
     
        if not valid_emails:
            console.print(Panel.fit(
                "[bold]PILIH METODE INPUT EMAIL[/bold]",
                border_style=current_settings['ui']['custom_theme']['primary_color'],
                width=min(shutil.get_terminal_size().columns, 80)
            ))
            
            input_method = Prompt.ask(
                "Pilih metode input email",
                choices=["1", "2"],
                default="1"
            )
            
            if input_method == "1":
           
                emails_input = Prompt.ask(
                    f"[yellow]Masukkan email[/yellow]"
                )
                emails = re.split(r'[,\s]+', emails_input.strip())
            else:
       
                file_path = Prompt.ask(
                    f"[yellow]Masukkan path file .txt berisi daftar email[/yellow]"
                )
                emails = load_emails_from_file(file_path)
                if emails is None:
                    continue
            
            console.print(f"[{current_settings['ui']['custom_theme']['info_color']}]Memvalidasi akun...[/]")
            valid_emails = []
            with ThreadPoolExecutor(max_workers=current_settings['basic']['max_workers']) as executor:
                futures = [executor.submit(validate_account, email) for email in emails if validate_email(email)]
                for i, future in enumerate(as_completed(futures)):
                    if future.result():
                        valid_emails.append(emails[i])
            
            if not valid_emails:
                console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Tidak ada email yang valid. Silakan coba lagi.[/]")
                continue
      
        console.print(Panel.fit(
            "[bold]MENU UTAMA[/bold]",
            border_style=current_settings['ui']['custom_theme']['primary_color'],
            width=min(shutil.get_terminal_size().columns, 80)
        ))
        
        table = Table.grid(padding=(1, 4))
        table.add_column("Menu", style=current_settings['ui']['custom_theme']['info_color'])
        table.add_column("Deskripsi", style="white")
        
        table.add_row("1", "⬆️  Upgrade VIP semua email")
        table.add_row("2", "⏳  Perpanjang VIP semua email")
        table.add_row("3", "🔄  Set VIP Permanen")
        table.add_row("4", "🔍  Cek Status VIP (Bulk)")
        table.add_row("5", "✏️  Ganti daftar email")
        table.add_row("6", "ℹ️  Tampilkan info akun")
        table.add_row("7", "⚙️  Pengaturan")
        table.add_row("8", "📜  Changelog")
        table.add_row("9", "🚪  Keluar")
        
        console.print(table)
        
        choice = Prompt.ask(
            "Pilih menu",
            choices=["1", "2", "3", "4", "5", "6", "7", "8", "9"],
            default="9"
        )
        
        if choice == '1':
            console.print(Panel.fit(
                "[bold]PROSES UPGRADE VIP[/bold]",
                border_style="yellow",
                width=min(shutil.get_terminal_size().columns, 80)
            ))
            process_multiple_emails(valid_emails)
            
        elif choice == '2':
            console.print(Panel.fit(
                "[bold]PROSES PERPANJANGAN VIP[/bold]",
                border_style="yellow",
                width=min(shutil.get_terminal_size().columns, 80)
            ))
            process_multiple_emails(valid_emails, is_extend=True)
            
        elif choice == '3':
            console.print(Panel.fit(
                "[bold]PROSES SET VIP PERMANEN[/bold]",
                border_style="yellow",
                width=min(shutil.get_terminal_size().columns, 80)
            ))
            process_multiple_emails(valid_emails, is_permanent=True)
            
        elif choice == '4':
            check_vip_bulk(valid_emails)
            
        elif choice == '5':
            valid_emails = []
            
        elif choice == '6':
            console.print(Panel.fit(
                "[bold]INFO AKUN[/bold]",
                border_style=current_settings['ui']['custom_theme']['primary_color'],
                width=min(shutil.get_terminal_size().columns, 80)
            ))
            with ThreadPoolExecutor(max_workers=current_settings['basic']['max_workers']) as executor:
                futures = [executor.submit(lambda e: (e, login(e)), email) for email in valid_emails]
                for future in as_completed(futures):
                    email, token = future.result()
                    if token:
                        get_data(token, email)
            
        elif choice == '7':
            show_settings_menu()
            
        elif choice == '8':
            display_changelog()
            input("\nTekan Enter untuk melanjutkan...")
            
        elif choice == '9':
            if Confirm.ask(f"[{current_settings['ui']['custom_theme']['error_color']}]Apakah Anda yakin ingin keluar?[/]"):
                if current_settings['security']['clear_cache_on_exit']:
                
                    pass
                
                stop_autosave()
                console.print(Panel.fit(
                    f"[{current_settings['ui']['custom_theme']['success_color']}]Terima kasih telah menggunakan scirpt ini![/]",
                    border_style=current_settings['ui']['custom_theme']['success_color'],
                    width=min(shutil.get_terminal_size().columns, 80)
                ))
                return

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print(f"\n[{current_settings['ui']['custom_theme']['error_color']}]✖ by by[/]")
        stop_autosave()
    except Exception as e:
        console.print(f"[{current_settings['ui']['custom_theme']['error_color']}]✖ Terjadi kesalahan: {str(e)}[/]")
        stop_autosave()