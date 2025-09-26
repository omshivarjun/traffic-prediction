import { NextRequest, NextResponse } from 'next/server';
import { trafficService } from '@/lib/services/trafficService';

/**
 * GET /api/traffic/predict
 * Returns traffic prediction for a specific location and time
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const latitude = searchParams.get('latitude');
  const longitude = searchParams.get('longitude');
  const targetDate = searchParams.get('targetDate');

  if (!latitude || !longitude) {
    return NextResponse.json(
      { error: 'Latitude and longitude are required' },
      { status: 400 }
    );
  }

  try {
    const prediction = await trafficService.predictTrafficForLocation(
      parseFloat(latitude),
      parseFloat(longitude),
      targetDate ? new Date(targetDate) : new Date()
    );
    
    return NextResponse.json(prediction);
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to generate traffic prediction' },
      { status: 500 }
    );
  }
}