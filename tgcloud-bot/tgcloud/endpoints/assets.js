// Owner-only: lists the current video's assets; with { id } also returns that file as base64.
import { api, db, EndpointError } from 'sdk';
import { eq } from 'sdk/db';
import { assets } from '../schema.js';
import { OWNER } from '../lib/config.js';

export default async function (input, ctx) {
  if (ctx.initData?.user?.id !== OWNER) throw new EndpointError('Forbidden', { code: 'FORBIDDEN' });
  if (input.id) {
    const row = await db.select().from(assets).where(eq(assets.id, input.id)).get();
    if (!row?.fileId) throw new EndpointError('Not found', { code: 'NOT_FOUND' });
    const bytes = await api.getFileContent(row.fileId);
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return { ...row, size: bytes.length, base64: btoa(bin) };
  }
  return db.select().from(assets).all();
}
