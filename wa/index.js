#!/usr/bin/env node
/**
 * Canal WhatsApp para la red de agentes Capitán.
 *
 * Recibe mensajes de texto y los envía al orquestador (POST /wa/inbound).
 * El core resuelve el número al usuario registrado (via User.wa_phone) y
 * aplica RBAC según su rol. Números no registrados operan como "guest".
 *
 * Primera vez: muestra un QR en la terminal para vincular la cuenta.
 * Sesiones siguientes: reanuda sin QR desde ~/.local/share/capitan/wa-session/.
 *
 * Uso:
 *   cp .env.example .env   # configurar CORE_URL
 *   npm install
 *   node index.js
 *
 *   # o via systemd:
 *   systemctl --user start capitan-wa
 */

require("dotenv").config({ path: __dirname + "/.env" });

const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const fs = require("fs");
const path = require("path");

// ── Configuración ──────────────────────────────────────────────────────────────

const CORE_URL = process.env.CORE_URL || "http://localhost:8765";
const SESSION_PATH =
  process.env.WA_SESSION_PATH ||
  path.join(process.env.HOME, ".local/share/capitan/wa-session");

fs.mkdirSync(SESSION_PATH, { recursive: true });

// ── Cliente ────────────────────────────────────────────────────────────────────

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: SESSION_PATH }),
  puppeteer: {
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
    headless: true,
  },
});

client.on("qr", (qr) => {
  console.log("[WA] Escaneá el QR con tu teléfono para conectar:");
  qrcode.generate(qr, { small: true });
});

client.on("authenticated", () => {
  console.log("[WA] Sesión autenticada");
});

client.on("ready", () => {
  console.log(`[WA] Cliente listo. Core: ${CORE_URL}`);
});

client.on("auth_failure", (msg) => {
  console.error(`[WA] Error de autenticación: ${msg}`);
  process.exit(1);
});

client.on("disconnected", (reason) => {
  console.log(`[WA] Desconectado (${reason}). Reconectando en 10s...`);
  setTimeout(() => client.initialize(), 10_000);
});

// ── Mensajes entrantes ─────────────────────────────────────────────────────────

client.on("message", async (msg) => {
  if (msg.isGroupMsg) return;
  if (msg.type !== "chat") return; // solo texto (Etapa A — PTT en Etapa B)

  // Normalizar número: "5491155xxxxxx@c.us" → "+5491155xxxxxx"
  const phone = "+" + msg.from.replace("@c.us", "");
  const text = msg.body.trim();
  if (!text) return;

  console.log(`[WA] ${phone}: ${text}`);

  try {
    const res = await fetch(`${CORE_URL}/wa/inbound`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        from_number: phone,
        text,
        message_id: msg.id.id,
      }),
    });

    if (!res.ok) {
      console.error(`[WA] Error del core: HTTP ${res.status}`);
      await msg.reply("Ocurrió un error al procesar tu mensaje.");
      return;
    }

    const data = await res.json();
    if (data.response) {
      await msg.reply(data.response);
      console.log(`[WA] → ${phone}: ${data.response.slice(0, 80)}`);
    }
  } catch (err) {
    console.error(`[WA] Error de conexión con el core: ${err.message}`);
    await msg.reply("No pude conectar con el sistema. Intentá de nuevo.");
  }
});

// ── Arranque ───────────────────────────────────────────────────────────────────

console.log(`[WA] Iniciando cliente. Core: ${CORE_URL}`);
client.initialize();
