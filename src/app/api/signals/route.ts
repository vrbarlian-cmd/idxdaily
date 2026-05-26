import { NextResponse } from 'next/server';

// Early signals are not yet implemented in the new schema.
export async function GET() {
  return NextResponse.json([]);
}
