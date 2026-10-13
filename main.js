const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

// المسارات
const inputFile = path.join(__dirname, 'ChatExport_2026-10-13', 'result.json');
const outputJson = path.join(__dirname, 'ChatExport_2026-10-13', 'compressed.json');
const outputGz = path.join(__dirname, 'ChatExport_2026-10-13', 'compressed.json.gz');

console.log('جاري قراءة الملف الأصلي...');
const raw = fs.readFileSync(inputFile, 'utf8');
const originalSizeMB = (Buffer.byteLength(raw, 'utf8') / (1024 * 1024)).toFixed(2);
console.log(`حجم الملف الأصلي: ${originalSizeMB} MB`);

console.log('جاري التحليل واستخراج البيانات الأساسية...');
const data = JSON.parse(raw);

// استخراج النص الصريح سواء كان نص عادي أو مصفوفة كائنات من تيليجرام
function extractText(text) {
  if (typeof text === 'string') return text;
  if (Array.isArray(text)) {
    return text
      .map(part => (typeof part === 'string' ? part : (part && part.text) || ''))
      .join('');
  }
  return '';
}

// ضغط كود المستخدم لتحويل "user123456" إلى رقم 123456 لتوفير أقصى مساحة
function parseUserId(fromId) {
  if (!fromId) return null;
  if (typeof fromId === 'number') return fromId;
  const match = fromId.match(/\d+/);
  return match ? Number(match[0]) : fromId;
}

const cleanedMessages = [];

for (const msg of (data.messages || [])) {
  // تجاهل رسائل النظام (مثل تغيير اسم القروب أو الصورة) إذا لم يكن لها نص أو صاحب
  if (msg.type !== 'message') continue;

  const text = extractText(msg.text);
  const userId = parseUserId(msg.from_id);

  // تمثيل مقتضب جداً:
  // d: date (ISO أو unix timestamp)
  // u: user_id
  // i: message_id
  // t: text
  // r: reply_to_message_id (اختياري فقط إذا وجد رد)
  const item = {
    i: msg.id,
    d: msg.date,
    u: userId,
    t: text
  };

  if (msg.reply_to_message_id) {
    item.r = msg.reply_to_message_id;
  }

  cleanedMessages.push(item);
}

console.log(`تمت معالجة وتصفية ${cleanedMessages.length} رسالة بنجاح.`);

// حفظ بصيغة JSON بدون مسافات (Minified)
const jsonString = JSON.stringify(cleanedMessages);
fs.writeFileSync(outputJson, jsonString, 'utf8');

const jsonSizeMB = (fs.statSync(outputJson).size / (1024 * 1024)).toFixed(2);
console.log(`حجم الملف المخفف (JSON): ${jsonSizeMB} MB`);

// ضغط إضافي باستخدام Gzip بأعلى مستوى ضغط (Level 9)
console.log('جاري ضغط الملف إلى GZIP (أقصى ضغط ممكن)...');
const gzipBuffer = zlib.gzipSync(Buffer.from(jsonString, 'utf8'), { level: 9 });
fs.writeFileSync(outputGz, gzipBuffer);

const gzSizeMB = (fs.statSync(outputGz).size / (1024 * 1024)).toFixed(2);
console.log(`حجم الملف المضغوط (GZ): ${gzSizeMB} MB`);

console.log('\n--- النتيجة النهائية ---');
console.log(`الأصلي:       ${originalSizeMB} MB`);
console.log(`المخفف JSON:  ${jsonSizeMB} MB (توفير بنسبة ${((1 - jsonSizeMB / originalSizeMB) * 100).toFixed(1)}%)`);
console.log(`المضغوط GZ:   ${gzSizeMB} MB (توفير بنسبة ${((1 - gzSizeMB / originalSizeMB) * 100).toFixed(1)}%)`);
console.log(`\nتم حفظ الملفات في مجلد ChatExport_2026-10-13:`);
console.log(`1. compressed.json`);
console.log(`2. compressed.json.gz (للأرشيف والنقل فائق الصغر)`);
