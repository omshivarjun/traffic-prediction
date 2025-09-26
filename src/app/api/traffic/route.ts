import { NextRequest, NextResponse } from 'next/server';
import { trafficService } from '@/lib/services/trafficService';

/**
 * GET /api/traffic
 * Returns all traffic data or filtered by location
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const latitude = searchParams.get('latitude');
  const longitude = searchParams.get('longitude');

  try {
    if (latitude && longitude) {
      const data = await trafficService.getTrafficData(
        parseFloat(latitude),
        parseFloat(longitude)
      );
      return NextResponse.json(data);
    } else {
      const data = await trafficService.getAllTrafficData();
      return NextResponse.json(data);
    }
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch traffic data' },
      { status: 500 }
    );
  }
}

/**
 * POST /api/traffic
 * Adds new traffic data
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const newData = await trafficService.addTrafficData(body);
    return NextResponse.json(newData, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to add traffic data' },
      { status: 500 }
    );
  }
}