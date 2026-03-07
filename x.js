// Simple Telegram Bot for GitHub Monitoring
// MULTI USER - HANYA KIRIM KALAU libMyLibName.so YANG BERUBAH
// WAKTU MENGGUNAKAN WIB (UTC+7)

const https = require('https');

// ========== KONFIGURASI ==========
const TELEGRAM_TOKEN = '8576374976:AAFqoBHnXqyaaMc8HrlU9qaeuZXeGUgI5Pg';
const GITHUB_REPO = 'DevZhii/libLoaderVeloura';
const TARGET_FILE = 'libMyLibName.so';      // File yang dipantau
const OUTPUT_FILENAME = 'librudp.bytes'; // Nama file saat dikirim
const CHECK_INTERVAL = 300000; // 5 menit
// =================================

// Store data per user
let userData = new Map(); // { chatId: { lastFileSha: '...' } }
let lastUpdateId = 0;
let globalLastFileSha = null; // SHA terakhir dari file target

// ========== FUNGSI HELPER WAKTU WIB ==========
function getWIBTime() {
  const now = new Date();
  // UTC+7 untuk WIB
  const wibTime = new Date(now.getTime() + (7 * 60 * 60 * 1000));
  
  const day = wibTime.getUTCDate().toString().padStart(2, '0');
  const month = (wibTime.getUTCMonth() + 1).toString().padStart(2, '0');
  const year = wibTime.getUTCFullYear();
  const hours = wibTime.getUTCHours().toString().padStart(2, '0');
  const minutes = wibTime.getUTCMinutes().toString().padStart(2, '0');
  const seconds = wibTime.getUTCSeconds().toString().padStart(2, '0');
  
  return {
    date: `${day}/${month}/${year}`,
    time: `${hours}:${minutes}:${seconds}`,
    datetime: `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`,
    datetimeShort: `${day}/${month}/${year}, ${hours}.${minutes}`
  };
}

// ========== FUNGSI KIRIM PESAN ==========
function sendToUser(chatId, text) {
  const url = `https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage`;
  const data = JSON.stringify({
    chat_id: chatId,
    text: text,
    parse_mode: 'Markdown'
  });

  const options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': data.length
    }
  };

  const req = https.request(url, options);
  req.on('error', (error) => console.error('[Telegram Error]', error.message));
  req.write(data);
  req.end();
}

// Fungsi kirim file ke user tertentu
function sendFileToUser(chatId, fileBuffer, filename, caption = '') {
  const boundary = '----boundary' + Date.now();
  let payload = '';
  
  payload += '--' + boundary + '\r\n';
  payload += 'Content-Disposition: form-data; name="chat_id"\r\n';
  payload += '\r\n';
  payload += chatId + '\r\n';
  
  if (caption) {
    payload += '--' + boundary + '\r\n';
    payload += 'Content-Disposition: form-data; name="caption"\r\n';
    payload += '\r\n';
    payload += caption + '\r\n';
    
    payload += '--' + boundary + '\r\n';
    payload += 'Content-Disposition: form-data; name="parse_mode"\r\n';
    payload += '\r\n';
    payload += 'Markdown\r\n';
  }
  
  payload += '--' + boundary + '\r\n';
  payload += `Content-Disposition: form-data; name="document"; filename="${filename}"\r\n`;
  payload += 'Content-Type: application/octet-stream\r\n';
  payload += '\r\n';
  
  const payloadBuffer = Buffer.from(payload, 'utf-8');
  const footerBuffer = Buffer.from('\r\n--' + boundary + '--\r\n', 'utf-8');
  
  const totalLength = payloadBuffer.length + fileBuffer.length + footerBuffer.length;
  const finalBuffer = Buffer.concat([payloadBuffer, fileBuffer, footerBuffer]);
  
  const options = {
    hostname: 'api.telegram.org',
    path: `/bot${TELEGRAM_TOKEN}/sendDocument`,
    method: 'POST',
    headers: {
      'Content-Type': `multipart/form-data; boundary=${boundary}`,
      'Content-Length': totalLength
    }
  };

  const req = https.request(options);
  req.on('error', (error) => console.error('[Telegram Error Kirim File]', error.message));
  req.write(finalBuffer);
  req.end();
}

// ========== FUNGSI GITHUB ==========
// Ambil SHA file tertentu dari GitHub
function getFileSha() {
  return new Promise((resolve) => {
    const url = `https://api.github.com/repos/${GITHUB_REPO}/contents/${TARGET_FILE}`;
    
    https.get(url, { headers: { 'User-Agent': 'Telegram-Bot' } }, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          if (res.statusCode === 200) {
            const info = JSON.parse(data);
            resolve(info.sha); // Ambil SHA file
          } else {
            resolve(null);
          }
        } catch { resolve(null); }
      });
    }).on('error', () => resolve(null));
  });
}

function downloadFile() {
  return new Promise((resolve) => {
    const url = `https://raw.githubusercontent.com/${GITHUB_REPO}/main/${TARGET_FILE}`;
    
    https.get(url, (res) => {
      if (res.statusCode === 200) {
        const chunks = [];
        res.on('data', (chunk) => chunks.push(chunk));
        res.on('end', () => resolve(Buffer.concat(chunks)));
      } else if (res.statusCode === 404) {
        const masterUrl = `https://raw.githubusercontent.com/${GITHUB_REPO}/master/${TARGET_FILE}`;
        https.get(masterUrl, (res2) => {
          if (res2.statusCode === 200) {
            const chunks = [];
            res2.on('data', (chunk) => chunks.push(chunk));
            res2.on('end', () => resolve(Buffer.concat(chunks)));
          } else {
            resolve(null);
          }
        }).on('error', () => resolve(null));
      } else {
        resolve(null);
      }
    }).on('error', () => resolve(null));
  });
}

function getFileInfo() {
  return new Promise((resolve) => {
    const url = `https://api.github.com/repos/${GITHUB_REPO}/contents/${TARGET_FILE}`;
    
    https.get(url, { headers: { 'User-Agent': 'Telegram-Bot' } }, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          if (res.statusCode === 200) resolve(JSON.parse(data));
          else resolve(null);
        } catch { resolve(null); }
      });
    }).on('error', () => resolve(null));
  });
}

// ========== HANDLE COMMANDS ==========
function handleTelegramCommands() {
  setInterval(() => {
    const url = `https://api.telegram.org/bot${TELEGRAM_TOKEN}/getUpdates?offset=${lastUpdateId + 1}&timeout=30`;
    
    https.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          const updates = JSON.parse(data);
          if (updates.result && updates.result.length > 0) {
            updates.result.forEach(update => {
              lastUpdateId = update.update_id;
              const msg = update.message;
              if (!msg || !msg.text) return;
              
              const chatId = msg.chat.id;
              const text = msg.text;
              const username = msg.from.username || msg.from.first_name || 'User';
              
              console.log(`[${username} (${chatId})] ${text}`);
              
              // Initialize user data if not exists
              if (!userData.has(chatId)) {
                userData.set(chatId, {
                  lastFileSha: null
                });
              }
              
              // HANDLE COMMANDS
              if (text === '/start') {
                sendToUser(chatId,
                  `hi ${username}\n\n` +
                  `there's nothing here lol\n\n` +
                  `fuck u indians\n` +
                  `/getfile\n` +
                  `/status\n` +
                  `/necro\n` +
                  `/help\n\n` +
                  `@zhii`
                );
              }
              else if (text === '/status') {
                const userLastSha = userData.get(chatId).lastFileSha;
                sendToUser(chatId,
                  `status necro\n\n` +
                  `status : nonactive\n` +
                  `no update lol'}`
                );
              }
              else if (text === '/necro') {
                sendToUser(chatId, 'wait');
                downloadFile().then(fileData => {
                  if (fileData) {
                    const size = (fileData.length / 1024).toFixed(2);
                    const wib = getWIBTime();
                    sendFileToUser(chatId, fileData, OUTPUT_FILENAME,
                      `necromod\n` +
                      ` ${size} KB\n` +
                      ` ${wib.datetimeShort} WIB`
                    );
                  } else {
                    sendToUser(chatId, `❌ File tidak tersedia`);
                  }
                });
              }
              else if (text === '/info') {
                getFileInfo().then(info => {
                  if (info) {
                    const size = (info.size / 1024).toFixed(2);
                    const wib = getWIBTime();
                    sendToUser(chatId,
                      `necro\n\n` +
                      `size : ${size} kb\n` +
                      `last update: ${wib.date}`
                    );
                  } else {
                    sendToUser(chatId, `file not found`);
                  }
                });
              }
              else if (text === '/help') {
                sendToUser(chatId,
                  `📚 *Bantuan*\n\n` +
                  `/start - Mulai bot\n` +
                  `/status - Cek status\n` +
                  `/getfile - Download file\n` +
                  `/info - Info file\n` +
                  `/help - Pesan ini\n\n` +
                  `Bot otomatis kirim file saat ada update.`
                );
              }
            });
          }
        } catch (e) {}
      });
    }).on('error', () => {});
  }, 1000);
}

// ========== AUTO CHECK UPDATE ==========
// Fungsi ini HANYA cek file TARGET_FILE, bukan semua file
async function autoCheck() {
  console.log('[Check] Mengecek file:', TARGET_FILE);
  
  const currentFileSha = await getFileSha();
  if (!currentFileSha) {
    console.log('[Check] Gagal ambil SHA file');
    return;
  }
  
  const shortSha = currentFileSha.substring(0, 8);
  
  // First run - catat SHA file
  if (!globalLastFileSha) {
    globalLastFileSha = currentFileSha;
    console.log(`[Init] File SHA: ${shortSha}`);
    return;
  }
  
  // Ada update file - KIRIM KE SEMUA USER
  if (globalLastFileSha !== currentFileSha) {
    console.log(`[UPDATE FILE] ${globalLastFileSha.substring(0, 8)} -> ${shortSha}`);
    
    const fileData = await downloadFile();
    if (fileData) {
      const size = (fileData.length / 1024).toFixed(2);
      const wib = getWIBTime();
      
      // Kirim ke SEMUA user yang pernah interact
      for (let [chatId, data] of userData.entries()) {
        console.log(`[Kirim ke ${chatId}]`);
        sendFileToUser(chatId, fileData, OUTPUT_FILENAME,
          `🆕 *Auto Update*\n` +
          `Ukuran: ${size} KB\n` +
          `Waktu: ${wib.datetimeShort} WIB`
        );
        
        // Update SHA user
        data.lastFileSha = currentFileSha;
      }
      
      globalLastFileSha = currentFileSha;
    } else {
      console.log('[Update] Gagal download file');
    }
  } else {
    console.log(`[Check] Tidak ada update (${shortSha})`);
  }
}

// ========== START BOT ==========
console.log('🚀 GitHub Monitor Bot - FILE SPECIFIC MODE');
console.log('Repo:', GITHUB_REPO);
console.log('Monitoring File:', TARGET_FILE);
console.log('Output File:', OUTPUT_FILENAME);
console.log('Interval:', CHECK_INTERVAL/1000, 'detik');
console.log('Timezone: WIB (UTC+7)');
console.log('HANYA KIRIM KALAU FILE INI BERUBAH!');
console.log('Bot siap melayani banyak user!');

// Auto check berkala
setInterval(autoCheck, CHECK_INTERVAL);
autoCheck(); // Cek sekali

// Handler command
handleTelegramCommands();