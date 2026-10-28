/** The slice of D1Database the sign-up insert needs. D1Database satisfies it structurally. */
export interface SignupDb {
  prepare(sql: string): { bind(...values: unknown[]): { run(): Promise<unknown> } };
}

export interface SignupRow {
  email: string;
  inArea: boolean | null;
  lat: number | null;
  lng: number | null;
  utmSource: string | null;
  utmMedium: string | null;
  utmCampaign: string | null;
  referrer: string | null;
}

const UPSERT_SQL = `INSERT INTO signups (email,in_area,lat,lng,utm_source,utm_medium,utm_campaign,referrer)
VALUES (?1,?2,?3,?4,?5,?6,?7,?8)
ON CONFLICT(email) DO UPDATE SET
  in_area=COALESCE(in_area,excluded.in_area), lat=COALESCE(lat,excluded.lat), lng=COALESCE(lng,excluded.lng),
  utm_source=COALESCE(utm_source,excluded.utm_source), utm_medium=COALESCE(utm_medium,excluded.utm_medium),
  utm_campaign=COALESCE(utm_campaign,excluded.utm_campaign), referrer=COALESCE(referrer,excluded.referrer),
  updated_at=datetime('now')`;

export async function upsertSignup(db: SignupDb, row: SignupRow): Promise<void> {
  const inArea = row.inArea === null ? null : row.inArea ? 1 : 0;
  await db
    .prepare(UPSERT_SQL)
    .bind(row.email, inArea, row.lat, row.lng, row.utmSource, row.utmMedium, row.utmCampaign, row.referrer)
    .run();
}
