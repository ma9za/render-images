// Owner-only: sets the bot's command menu and description, returns the bot's identity.
import { api, EndpointError } from 'sdk';
import { OWNER } from '../lib/config.js';

export default async function (input, ctx) {
  if (ctx.initData?.user?.id !== OWNER) throw new EndpointError('Forbidden', { code: 'FORBIDDEN' });
  await api.setMyCommands({ commands: [
    { command: 'start', description: 'طريقة الشغل' },
    { command: 'new', description: 'فيديو جديد' },
    { command: 'list', description: 'وش استلمت' },
  ] });
  await api.setMyDescription({ description: 'بوت الرندر حق تركي: أرسل الصوت والصور، ويرجع لك الفيديو جاهز.' });
  await api.setMyShortDescription({ short_description: 'بوت الرندر حق تركي' });
  return api.getMe();
}
