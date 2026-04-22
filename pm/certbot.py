"""Integração com Certbot."""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path

from pm.data import log_action


def is_installed() -> bool:
    return shutil.which("certbot") is not None


def cert_exists(domain: str) -> bool:
    return Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem").exists()


def issue_cert(domain: str, email: str) -> tuple[bool, str]:
    Path("/var/www/certbot").mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["certbot", "certonly", "--webroot", "-w", "/var/www/certbot",
         "-d", domain, "--email", email, "--agree-tos", "--non-interactive"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        log_action(f"Certificado emitido: {domain}")
    else:
        log_action(f"Erro ao emitir certificado: {domain}", "ERROR")
    return r.returncode == 0, r.stdout + r.stderr


def renew_cert(domain: str) -> tuple[bool, str]:
    r = subprocess.run(
        ["certbot", "renew", "--cert-name", domain, "--non-interactive"],
        capture_output=True, text=True,
    )
    return r.returncode == 0, r.stdout + r.stderr


def delete_cert(domain: str) -> tuple[bool, str]:
    r = subprocess.run(
        ["certbot", "delete", "--cert-name", domain, "--non-interactive"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        log_action(f"Certificado removido: {domain}")
    return r.returncode == 0, r.stdout + r.stderr


def list_certs() -> list[str]:
    if not is_installed():
        return []
    r = subprocess.run(["certbot", "certificates"], capture_output=True, text=True)
    return [l.split("Domains:")[-1].strip()
            for l in r.stdout.splitlines() if "Domains:" in l]


def has_cron() -> bool:
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        return "certbot renew" in r.stdout
    except FileNotFoundError:
        return False

def toggle_cron() -> bool:
    if not shutil.which("crontab"):
        log_action("Comando 'crontab' não encontrado.", "ERROR")
        return False
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = r.stdout.splitlines()
    if any("certbot renew" in l for l in lines):
        new_lines = [l for l in lines if "certbot renew" not in l]
        new_cron = "\n".join(new_lines) + "\n" if new_lines else ""
        subprocess.run(["crontab", "-"], input=new_cron, capture_output=True, text=True)
        log_action("Cron de renovação SSL removido")
        return False
    else:
        cron_line = "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'"
        new_cron = "\n".join(lines) + ("\n" if lines else "") + cron_line + "\n"
        subprocess.run(["crontab", "-"], input=new_cron, capture_output=True, text=True)
        log_action("Cron de renovação SSL configurado")
        return True
