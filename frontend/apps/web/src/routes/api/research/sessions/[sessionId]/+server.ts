/**
 * Copyright (c) 2025 Sundsvalls Kommun
 *
 * This file is part of Eneo.
 * Licensed under the AGPL-3.0 License.
 * See LICENSE file in the project root for full license information.
 */

import { env } from "$env/dynamic/private";
import type { RequestHandler } from "./$types";

export const GET: RequestHandler = async ({ params, locals }) => {
  const { sessionId } = params;

  if (!locals.id_token) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" }
    });
  }

  try {
    const response = await fetch(
      `${env.INTRIC_BACKEND_URL}/api/v1/research/api/research/sessions/${sessionId}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${locals.id_token}`
        }
      }
    );

    if (!response.ok) {
      const error = await response.text();
      return new Response(error, {
        status: response.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    const data = await response.json();
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    console.error("Get session proxy error:", error);
    return new Response(JSON.stringify({ error: "Failed to get session" }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
};

export const DELETE: RequestHandler = async ({ params, locals }) => {
  const { sessionId } = params;

  if (!locals.id_token) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" }
    });
  }

  try {
    const response = await fetch(
      `${env.INTRIC_BACKEND_URL}/api/v1/research/api/research/sessions/${sessionId}`,
      {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${locals.id_token}`
        }
      }
    );

    if (!response.ok) {
      const error = await response.text();
      return new Response(error, {
        status: response.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    return new Response(null, { status: 204 });
  } catch (error) {
    console.error("Cancel session proxy error:", error);
    return new Response(JSON.stringify({ error: "Failed to cancel session" }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
};