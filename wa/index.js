#!/usr/bin/env node
/**
 * Canal WhatsApp para la red de agentes Capitán.
 *
 * - Texto: POST /wa/inbound → responde texto
 * - PTT/audio: descarga OGG → POST /wa/inbound/audio → responde nota de voz
 *
 * El core resuelve el número al usuario registrado (User.wa_phone) y aplica
 * RBAC según su rol. Números no registrados operan como "guest".
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

const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const fs   = require("fs");
const http = require("http");
const path = require("path");

// ── Configuración ──────────────────────────────────────────────────────────────

const CORE_URL = process.env.CORE_URL || "http://localhost:8765";
const WA_PORT  = parseInt(process.env.WA_PORT || "3001", 10);
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

// ── Helpers ────────────────────────────────────────────────────────────────────

async function handleText(msg, phone, fromLid, text) {
  const body = { text, message_id: msg.id.id };
  if (phone)   body.from_number = phone;
  if (fromLid) body.from_lid    = fromLid;

  const res = await fetch(`${CORE_URL}/wa/inbound`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    console.error(`[WA] Error del core: HTTP ${res.status}`);
    await msg.reply("Ocurrió un error al procesar tu mensaje.");
    return;
  }

  const data = await res.json();
  if (data.response) {
    await msg.reply(data.response);
    console.log(`[WA] → ${phone || fromLid}: ${data.response.slice(0, 80)}`);
  }
}

async function handleAudio(msg, phone, fromLid) {
  const media = await msg.downloadMedia();
  if (!media) {
    console.error(`[WA] No se pudo descargar el audio de ${phone || fromLid}`);
    return;
  }

  const body = { audio_b64: media.data, message_id: msg.id.id };
  if (phone)   body.from_number = phone;
  if (fromLid) body.from_lid    = fromLid;

  const res = await fetch(`${CORE_URL}/wa/inbound/audio`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    console.error(`[WA] Error del core (audio): HTTP ${res.status}`);
    await msg.reply("No pude procesar el audio. Intentá con texto.");
    return;
  }

  const data = await res.json();
  console.log(`[WA] STT ${phone || fromLid}: "${data.transcription}"`);

  if (data.audio_b64) {
    const voiceNote = new MessageMedia(
      "audio/ogg; codecs=opus",
      data.audio_b64,
      "response.ogg"
    );
    const chat = await msg.getChat();
    await chat.sendMessage(voiceNote, { sendAudioAsVoice: true });
    console.log(`[WA] → ${phone || fromLid}: [nota de voz] ${data.response.slice(0, 60)}`);
  } else if (data.response) {
    await msg.reply(data.response);
    console.log(`[WA] → ${phone || fromLid}: ${data.response.slice(0, 80)}`);
  }
}

// ── Mensajes entrantes ─────────────────────────────────────────────────────────

client.on("message", async (msg) => {
  if (msg.isGroupMsg) return;

  // msg.from puede ser "5491155...@c.us" o "205432...@lid" (linked identity, WA moderno).
  // Estrategia: getChat() → contact.id → msg.from (en ese orden de confiabilidad).
  let phone = null;
  let fromLid = null;

  try {
    const chat  = await msg.getChat();
    const chatId = chat.id._serialized;

    if (chatId.endsWith("@c.us")) {
      phone = "+" + chat.id.user;
    } else {
      // Chat también en @lid — extraer LID para match en el core
      if (chatId.endsWith("@lid")) fromLid = chat.id.user;

      // Intentar vía contacto
      const contact = await msg.getContact();
      if (contact.id._serialized.endsWith("@c.us")) {
        phone = "+" + contact.id.user;
      } else if (contact.id._serialized.endsWith("@lid")) {
        fromLid = fromLid || contact.id.user;
      }
    }
  } catch (_) {
    // noop — usamos fromLid o fallback
  }

  if (!phone && !fromLid) {
    // Último recurso: extraer lo que sea del from
    fromLid = msg.from.replace(/@\S+/, "");
  }

  console.log(`[WA] from=${msg.from} → phone=${phone} lid=${fromLid}`);

  try {
    if (msg.type === "chat") {
      const text = msg.body.trim();
      if (!text) return;
      console.log(`[WA] texto ${phone || fromLid}: ${text}`);
      await handleText(msg, phone, fromLid, text);
    } else if (msg.type === "ptt" || msg.type === "audio") {
      console.log(`[WA] audio ${phone || fromLid} (${msg.type})`);
      await handleAudio(msg, phone, fromLid);
    }
  } catch (err) {
    console.error(`[WA] Error inesperado: ${err.message}`);
    await msg.reply("Ocurrió un error interno. Intentá de nuevo.").catch(() => {});
  }
});

// ── Servidor HTTP outbound ─────────────────────────────────────────────────────

http.createServer(async (req, res) => {
  if (req.method !== "POST" || req.url !== "/send") {
    res.writeHead(404);
    res.end();
    return;
  }

  let body = "";
  req.on("data", (chunk) => { body += chunk; });
  req.on("end", async () => {
    try {
      const { to, text, audio_b64 } = JSON.parse(body);
      if (!to || (!text && !audio_b64)) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "to y (text o audio_b64) son requeridos" }));
        return;
      }
      const chatId = to.replace("+", "") + "@c.us";

      if (audio_b64) {
        const voiceNote = new MessageMedia("audio/ogg; codecs=opus", audio_b64, "notification.ogg");
        const chat = await client.getChatById(chatId);
        await chat.sendMessage(voiceNote, { sendAudioAsVoice: true });
        console.log(`[WA] → ${to}: [nota de voz]`);
      } else {
        await client.sendMessage(chatId, text);
        console.log(`[WA] → ${to}: ${text.slice(0, 80)}`);
      }

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true }));
    } catch (err) {
      console.error(`[WA] Error outbound: ${err.message}`);
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: err.message }));
    }
  });
}).listen(WA_PORT, "127.0.0.1", () => {
  console.log(`[WA] Servidor outbound escuchando en :${WA_PORT}`);
});


// ── Arranque ───────────────────────────────────────────────────────────────────

console.log(`[WA] Iniciando cliente. Core: ${CORE_URL}`);
client.initialize();
