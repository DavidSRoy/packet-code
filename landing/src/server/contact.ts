import type { ContactInput } from "../lib/contact-input.ts";
import type { SignupDb } from "./signups.ts";

const INSERT_SQL = `INSERT INTO contact_messages (topic,name,email,org,message,utm_source,utm_medium,utm_campaign,referrer)
VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9)`;

export async function insertContact(db: SignupDb, row: ContactInput): Promise<void> {
  await db
    .prepare(INSERT_SQL)
    .bind(row.topic, row.name, row.email, row.org, row.message, row.utmSource, row.utmMedium, row.utmCampaign, row.referrer)
    .run();
}
