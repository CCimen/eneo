import { json, error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async (event) => {
  try {
    const { sessionId } = event.params;
    
    const response = await event.fetch(
      `${env.INTRIC_BACKEND_URL}/api/v1/research/api/research/sessions/${sessionId}/plan`,
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
    console.error('Research plan API proxy error:', err);
    throw error(500, 'Failed to get research plan');
  }
};