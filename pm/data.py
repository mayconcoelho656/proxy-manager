"""Modelos de dados e CRUD para VMs e Domínios."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DATA_DIR    = Path("/etc/proxy-manager")
VMS_FILE    = DATA_DIR / "vms.conf"
DOMAINS_FILE= DATA_DIR / "domains.conf"
BACKUP_DIR  = DATA_DIR / "backups"
LOG_FILE    = Path("/var/log/proxy-manager.log")

# ── Modelos ───────────────────────────────────────────────────────────────────

@dataclass
class VM:
    nome:        str
    ip:          str
    porta_http:  str = "80"
    porta_https: str = "443"
    http_on:     str = "on"
    https_on:    str = "on"
    modo:        str = "passthrough"   # passthrough | termination
    descricao:   str = ""

    @classmethod
    def from_line(cls, line: str) -> Optional["VM"]:
        p = line.strip().split("|")
        if len(p) < 2:
            return None
        while len(p) < 8:
            p.append("")
        return cls(*p[:8])

    def to_line(self) -> str:
        return "|".join([self.nome, self.ip, self.porta_http, self.porta_https,
                         self.http_on, self.https_on, self.modo, self.descricao])

    @property
    def cert_count(self) -> int:
        from pm.data import load_domains
        return sum(1 for d in load_domains() if d.vm_nome == self.nome)


@dataclass
class Domain:
    dominio:      str
    vm_nome:      str
    tipo:         str = "ambos"   # http | https | ambos
    backend_port: str = ""
    email_ssl:    str = ""
    auto_renew:   str = "on"

    @classmethod
    def from_line(cls, line: str) -> Optional["Domain"]:
        p = line.strip().split("|")
        if len(p) < 2:
            return None
        while len(p) < 6:
            p.append("")
        if not p[5]: p[5] = "on"
        return cls(*p[:6])

    def to_line(self) -> str:
        return "|".join([self.dominio, self.vm_nome, self.tipo,
                         self.backend_port, self.email_ssl, self.auto_renew])

    @property
    def cert_path(self) -> tuple[Optional[Path], Optional[Path]]:
        le_cert = Path(f"/etc/letsencrypt/live/{self.dominio}/fullchain.pem")
        le_key = Path(f"/etc/letsencrypt/live/{self.dominio}/privkey.pem")
        if le_cert.exists():
            return le_cert, le_key
        man_cert = Path(f"/etc/proxy-manager/certs/{self.dominio}/fullchain.pem")
        man_key = Path(f"/etc/proxy-manager/certs/{self.dominio}/privkey.pem")
        if man_cert.exists():
            return man_cert, man_key
        return None, None

    @property
    def has_cert(self) -> bool:
        return self.cert_path[0] is not None

    @property
    def cert_info(self) -> tuple[str, str]:
        cert, _ = self.cert_path
        if not cert:
            return "Nenhum", "-"
        tipo = "Let's Encrypt" if "letsencrypt" in str(cert) else "Importado"
        
        import subprocess
        try:
            r = subprocess.run(["openssl", "x509", "-enddate", "-noout", "-in", str(cert)],
                               capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                raw = r.stdout.strip().replace("notAfter=", "")
                from datetime import datetime
                dt = datetime.strptime(raw, "%b %d %H:%M:%S %Y %Z")
                exp = dt.strftime("%d/%m/%Y")
            else:
                exp = "Desconhecido"
        except Exception:
            exp = "Erro"
            
        return tipo, exp


# ── Helpers de arquivo ────────────────────────────────────────────────────────

def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [l for l in path.read_text().splitlines() if l.strip()]

def _write_lines(path: Path, lines: list[str]) -> None:
    _ensure_dirs()
    path.write_text("\n".join(lines) + ("\n" if lines else ""))

# ── VMs ───────────────────────────────────────────────────────────────────────

def load_vms() -> list[VM]:
    return [v for l in _read_lines(VMS_FILE) if (v := VM.from_line(l))]

def save_vms(vms: list[VM]) -> None:
    _write_lines(VMS_FILE, [v.to_line() for v in vms])

def get_vm(nome: str) -> Optional[VM]:
    return next((v for v in load_vms() if v.nome == nome), None)

def add_vm(vm: VM) -> None:
    vms = load_vms()
    vms.append(vm)
    save_vms(vms)
    log_action(f"VM adicionada: {vm.nome} ({vm.ip}) modo={vm.modo}")

def update_vm(vm: VM) -> None:
    save_vms([vm if v.nome == vm.nome else v for v in load_vms()])
    log_action(f"VM atualizada: {vm.nome}")

def delete_vm(nome: str) -> None:
    save_vms([v for v in load_vms() if v.nome != nome])
    log_action(f"VM removida: {nome}")

# ── Domínios ──────────────────────────────────────────────────────────────────

def load_domains() -> list[Domain]:
    return [d for l in _read_lines(DOMAINS_FILE) if (d := Domain.from_line(l))]

def save_domains(domains: list[Domain]) -> None:
    _write_lines(DOMAINS_FILE, [d.to_line() for d in domains])

def get_domain(dominio: str) -> Optional[Domain]:
    return next((d for d in load_domains() if d.dominio == dominio), None)

def add_domain(domain: Domain) -> None:
    domains = load_domains()
    domains.append(domain)
    save_domains(domains)
    log_action(f"Domínio vinculado: {domain.dominio} → {domain.vm_nome}")

def update_domain(domain: Domain) -> None:
    save_domains([domain if d.dominio == domain.dominio else d for d in load_domains()])
    log_action(f"Domínio atualizado: {domain.dominio}")

def delete_domain(dominio: str) -> None:
    save_domains([d for d in load_domains() if d.dominio != dominio])
    log_action(f"Domínio removido: {dominio}")

# ── Log ───────────────────────────────────────────────────────────────────────

def log_action(msg: str, level: str = "INFO") -> None:
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with LOG_FILE.open("a") as f:
            f.write(f"[{ts}] [{level}] {msg}\n")
    except OSError:
        pass

def read_log(lines: int = 50) -> str:
    if not LOG_FILE.exists():
        return "(sem log)"
    all_lines = LOG_FILE.read_text().splitlines()
    return "\n".join(all_lines[-lines:])

def clear_log() -> None:
    if LOG_FILE.exists():
        LOG_FILE.write_text("")
    log_action("Log limpo pelo usuário")
