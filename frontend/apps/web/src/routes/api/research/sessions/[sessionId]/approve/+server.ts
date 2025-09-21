import { json, error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async (event) => {
  try {
    const { sessionId } = event.params;
    const body = await event.request.json();
    
    const response = await event.fetch(
      `${env.INTRIC_BACKEND_URL}/api/v1/research/api/research/sessions/${sessionId}/approve`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${event.locals.id_token}`
        },
        body: JSON.stringify(body)
      }
    );

    if (!response.ok) {
      const errorData = await response.text();
      throw error(response.status, errorData);
    }

    const result = await response.json();
    return json(result);
    
  } catch (err) {
    console.error('Research approve API proxy error:', err);
    throw error(500, 'Failed to approve research plan');
  }
};