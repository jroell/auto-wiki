import { NextRequest, NextResponse } from 'next/server';

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_HOST || 'http://localhost:8001';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function GET(_request: NextRequest, context: any) {
  const jobId = context?.params?.id as string | undefined;
  if (!jobId) {
    return NextResponse.json({ error: 'Job ID missing' }, { status: 400 });
  }
  try {
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/jobs/${jobId}`, { cache: 'no-store' });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      return NextResponse.json({ error: text }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
