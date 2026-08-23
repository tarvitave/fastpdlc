terraform {
  required_version = ">= 1.5"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }
}

# Token comes from the HCLOUD_TOKEN environment variable or terraform.tfvars.
# It is deliberately not defaulted — an empty token fails loudly.
provider "hcloud" {
  token = var.hcloud_token
}

# ── ssh key ────────────────────────────────────────────────────────────────
resource "hcloud_ssh_key" "deploy" {
  name       = "${var.project_name}-deploy"
  public_key = trimspace(file(pathexpand(var.ssh_public_key_path)))
}

# ── firewall: only ssh, http, https reach the box ──────────────────────────
resource "hcloud_firewall" "web" {
  name = "${var.project_name}-web"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.ssh_allowed_ips
    description = "ssh"
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
    description = "http (ACME challenge + redirect)"
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
    description = "https"
  }

  rule {
    direction  = "udp"
    protocol   = "udp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
    description = "http/3 (quic)"
  }
}

# ── the server ─────────────────────────────────────────────────────────────
resource "hcloud_server" "web" {
  name        = var.project_name
  server_type = var.server_type
  location    = var.location
  image       = var.image
  ssh_keys    = [hcloud_ssh_key.deploy.id]
  firewall_ids = [hcloud_firewall.web.id]

  # +20% of the server price. Worth it: this box holds the only copy of the
  # lead database until a CRM takes over.
  backups = var.enable_backups

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  user_data = templatefile("${path.module}/cloud-init.yaml", {
    deploy_user    = var.deploy_user
    ssh_public_key = trimspace(file(pathexpand(var.ssh_public_key_path)))
    remote_dir     = var.remote_dir
  })

  labels = {
    project = var.project_name
    managed = "terraform"
  }

  lifecycle {
    # Changing the image would rebuild the server and destroy its volumes.
    ignore_changes = [image]
  }
}
