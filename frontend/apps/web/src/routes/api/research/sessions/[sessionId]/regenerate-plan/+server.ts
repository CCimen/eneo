import { json, error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

export const PUT: RequestHandler = async (event) => {
  try {
    const { sessionId } = event.params;
    const { query } = await event.request.json();

    const response = await event.fetch(
      `${env.INTRIC_BACKEND_URL}/api/v1/research/api/research/sessions/${sessionId}/regenerate-plan`,
      {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${event.locals.id_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query })
      }
    );

    if (!response.ok) {
      const errorData = await response.text();
      throw error(response.status, errorData);
    }

    const result = await response.json();
    return json(result);

  } catch (err) {
    console.error('Regenerate plan API proxy error:', err);
    throw error(500, 'Failed to regenerate research plan');
  }
};