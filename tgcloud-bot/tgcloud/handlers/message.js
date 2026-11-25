// Receives the voice, images, clips and notes for the next video.
import { api, db } from 'sdk';
import { eq } from 'sdk/db';
import { assets } from '../schema.js';
import { OWNER, MSG, fmt, count } from '../lib/config.js';

export default async function (m) {
  const reply = (text) =>
    api.sendMessage({ chat_id: m.chat.id, text, reply_parameters: { message_id: m.message_id, allow_sending_without_reply: true } });

  if (m.from?.id !== OWNER) return reply(MSG.private);

  const text = (m.text || '').trim();
  if (text.startsWith('/start')) return reply(MSG.start);
  if (text.startsWith('/new')) {
    await db.delete(assets).run();
    return reply(MSG.fresh);
  }
  if (text.startsWith('/list')) return reply(await summary());

  const doc = m.document || {};
  const mime = doc.mime_type || '';

  const audio = m.voice || m.audio || (mime.startsWith('audio/') ? doc : null);
  if (audio) {
    const had = (await db.$count(assets, eq(assets.kind, 'voice'))) > 0;
    await db.delete(assets).where(eq(assets.kind, 'voice')).run();
    await db.insert(assets).values({
      kind: 'voice', fileId: audio.file_id, duration: audio.duration || 0,
      name: audio.file_name || 'voice.ogg',
    }).run();
    const d = fmt(audio.duration);
    return reply(had ? MSG.voiceReplaced(d) : MSG.voice(d));
  }

  if (m.photo || mime.startsWith('image/')) {
    const f = m.photo ? m.photo[m.photo.length - 1] : doc;
    const n = (await db.$count(assets, eq(assets.kind, 'image'))) + 1;
    await db.insert(assets).values({
      kind: 'image', fileId: f.file_id, name: doc.file_name || `image${n}.jpg`, caption: m.caption || null,
    }).run();
    return reply(MSG.image(count(n, 'صورة وحدة', 'صورتين', 'صور', 'صورة')));
  }

  const vid = m.video || m.animation || (mime.startsWith('video/') ? doc : null);
  if (vid) {
    const n = (await db.$count(assets, eq(assets.kind, 'clip'))) + 1;
    await db.insert(assets).values({
      kind: 'clip', fileId: vid.file_id, duration: vid.duration || 0,
      name: vid.file_name || `clip${n}.mp4`, caption: m.caption || null,
    }).run();
    return reply(MSG.clip(fmt(vid.duration), count(n, 'مقطع واحد', 'مقطعين', 'مقاطع', 'مقطع')));
  }

  if (doc.file_id) {
    await db.insert(assets).values({ kind: 'file', fileId: doc.file_id, name: doc.file_name || 'file', caption: m.caption || null }).run();
    return reply(`وصل الملف ✅\n${doc.file_name || ''}`);
  }

  if (text) {
    await db.insert(assets).values({ kind: 'note', caption: text }).run();
    return reply(MSG.note);
  }
  return reply(MSG.unknown);
}

async function summary() {
  const rows = await db.select().from(assets).all();
  if (!rows.length) return MSG.empty;
  const voice = rows.find((r) => r.kind === 'voice');
  const n = (k) => rows.filter((r) => r.kind === k).length;
  const lines = ['📋 اللي عندي للفيديو الحالي:', voice ? `الصوت: ${fmt(voice.duration)}` : 'الصوت: ما وصل',
    `الصور: ${n('image')}`, `المقاطع: ${n('clip')}`];
  if (n('note')) lines.push(`الملاحظات: ${n('note')}`);
  return lines.join('\n');
}
