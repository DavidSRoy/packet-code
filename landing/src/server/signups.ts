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
  in_area=COALESCE(excluded.in_area,in_area), lat=COALESCE(excluded.lat,lat), lng=COALESCE(excluded.lng,lng),
  utm_source=COALESCE(excluded.utm_source,utm_source), utm_medium=COALESCE(excluded.utm_medium,utm_medium),
  utm_campaign=COALESCE(excluded.utm_campaign,utm_campaign), referrer=COALESCE(excluded.referrer,referrer),
  updated_at=datetime('now')`;

export async function upsertSignup(db: SignupDb, row: SignupRow): Promise<void> {
  const inArea = row.inArea === null ? null : row.inArea ? 1 : 0;
  await db
    .prepare(UPSERT_SQL)
    .bind(row.email, inArea, row.lat, row.lng, row.utmSource, row.utmMedium, row.utmCampaign, row.referrer)
    .run();
}
