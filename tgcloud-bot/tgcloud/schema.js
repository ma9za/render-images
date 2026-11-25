import { table, integer, text, sql } from 'sdk/db';

// Files and notes Turki sent for the video he's working on now. /new clears it.
export const assets = table('assets', {
  id:       integer('id').primaryKey({ autoIncrement: true }),
  kind:     text('kind').notNull(),          // voice | image | clip | note
  fileId:   text('file_id'),
  name:     text('name'),
  duration: integer('duration').default(0),
  caption:  text('caption'),
  created:  integer('created_at').default(sql`(unixepoch())`),
});
