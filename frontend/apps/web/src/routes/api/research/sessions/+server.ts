import { json, error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async (event) => {
  try {
    const body = await event.request.json();
    
    // Proxy to FastAPI backend with proper authentication
    const response = await event.fetch(`${env.INTRIC_BACKEND_URL}/api/v1/research/api/research/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${event.locals.id_token}`
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const errorData = await response.text();
      throw error(response.status, errorData);
    }

    const result = await response.json();
    return json(result);
    
  } catch (err) {
    console.error('Research API proxy error:', err);
    throw error(500, 'Failed to create research session');
  }
};

export const GET: RequestHandler = async (event) => {
  try {
    // Handle query parameters for pagination/filtering
    const url = new URL(event.request.url);
    const queryParams = url.searchParams.toString();
    
    const response = await event.fetch(
      `${env.INTRIC_BACKEND_URL}/api/v1/research/api/research/sessions?${queryParams}`, 
      {
        headers: {
          'Authorization': `Bearer ${event.locals.id_token}`
        }
      }
    );

    if (!response.ok) {
      const errorData = await response.text();
      throw error(response.status, errorData);
    }

    const result = await response.json();
    return json(result);
    
  } catch (err) {
    console.error('Research API proxy error:', err);
    throw error(500, 'Failed to list research sessions');
  }
};