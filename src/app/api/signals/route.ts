import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// Early signals are not yet implemented in the new schema.
export async function GET() {
  return NextResponse.json([]);
}
