import { NextResponse } from 'next/server';

const BACKEND_BASE_URL =
  process.env.SERVER_BASE_URL ||
  process.env.PYTHON_BACKEND_HOST ||
  'http://localhost:8001';

export async function GET() {
  try {
    const targetUrl = `${BACKEND_BASE_URL}/lang/config`;
    const backendResponse = await fetch(targetUrl, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!backendResponse.ok) {
      return NextResponse.json(
        { error: `Backend service responded with status: ${backendResponse.status}` },
        { status: backendResponse.status },
      );
    }

    const config = await backendResponse.json();
    return NextResponse.json(config);
  } catch (error) {
    console.error('Error fetching language config:', error);
    return new NextResponse(JSON.stringify({ error: 'Failed to reach backend for lang config' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

export function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    },
  });
}
