// Owner-only: lists the current video's assets; with { id, offset, size } returns that file's bytes as base64, in chunks.
import { api, db, EndpointError } from 'sdk';
import { eq } from 'sdk/db';
import { assets } from '../schema.js';
import { OWNER } from '../lib/config.js';

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
function b64(u8) {
  let out = '';
  for (let i = 0; i < u8.length; i += 3) {
    const a = u8[i], b = u8[i + 1], c = u8[i + 2];
    out += B64[a >> 2] + B64[((a & 3) << 4) | ((b ?? 0) >> 4)] +
      (b === undefined ? '=' : B64[((b & 15) << 2) | ((c ?? 0) >> 6)]) + (c === undefined ? '=' : B64[c & 63]);
  }
  return out;
}

export default async function (input, ctx) {
  if (ctx.initData?.user?.id !== OWNER) throw new EndpointError('Forbidden', { code: 'FORBIDDEN' });
  if (input.id) {
    const row = await db.select().from(assets).where(eq(assets.id, input.id)).get();
    if (!row?.fileId) throw new EndpointError('Not found', { code: 'NOT_FOUND' });
    const bytes = await api.getFileContent(row.fileId);
    const off = input.offset || 0, size = input.size || 300000;   // multiple of 3 keeps chunks joinable
    return { id: row.id, name: row.name, total: bytes.length, offset: off, base64: b64(bytes.subarray(off, off + size)) };
  }
  return db.select().from(assets).all();
}
