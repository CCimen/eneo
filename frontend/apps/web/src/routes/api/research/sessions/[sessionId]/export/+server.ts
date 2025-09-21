/**
 * Copyright (c) 2025 Sundsvalls Kommun
 * 
 * This file is part of Eneo.
 * Licensed under the AGPL-3.0 License.
 * See LICENSE file in the project root for full license information.
 */

import { env } from "$env/dynamic/private";
import type { RequestHandler } from "./$types";

export const POST: RequestHandler = async ({ request, params, locals }) => {
  const { sessionId } = params;
  
  if (!locals.id_token) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" }
    });
  }

  const body = await request.json();
  
  try {
    const response = await fetch(
      `${env.INTRIC_BACKEND_URL}/api/v1/research/api/research/sessions/${sessionId}/export`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${locals.id_token}`
        },
        body: JSON.stringify(body)
      }
    );

    if (!response.ok) {
      const error = await response.text();
      return new Response(error, {
        status: response.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Get the content type and filename from the backend response
    const contentType = response.headers.get("Content-Type") || "application/octet-stream";
    const contentDisposition = response.headers.get("Content-Disposition") || "";
    
    const data = await response.arrayBuffer();
    
    return new Response(data, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": contentDisposition
      }
    });
  } catch (error) {
    console.error("Export proxy error:", error);
    return new Response(JSON.stringify({ error: "Export failed" }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
};