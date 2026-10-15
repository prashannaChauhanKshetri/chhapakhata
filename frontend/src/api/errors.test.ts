import { describe, expect, it } from 'vitest';

import { ApiError, errorMessage } from './errors';

describe('ApiError', () => {
  it('maps field errors to form paths and keeps a general message', () => {
    const error = ApiError.fromBody(400, {
      type: 'validation_error',
      errors: [
        { code: 'invalid', detail: 'Width must be greater than zero.', attr: 'items.0.width' },
        { code: 'business_rule', detail: 'Your discount limit is 10%.', attr: 'discount_value' },
      ],
    });
    expect(error.fieldErrors).toEqual({
      'items.0.width': 'Width must be greater than zero.',
      discount_value: 'Your discount limit is 10%.',
    });
    expect(error.message).toBe('Width must be greater than zero.');
  });

  it('prefers non-field errors for the summary', () => {
    const error = ApiError.fromBody(400, {
      errors: [
        { code: 'x', detail: 'Field problem', attr: 'name' },
        { code: 'y', detail: 'Incorrect username or password.', attr: 'non_field_errors' },
      ],
    });
    expect(error.summary).toBe('Incorrect username or password.');
  });

  it('recognises an expired session', () => {
    const error = ApiError.fromBody(403, {
      errors: [
        {
          code: 'not_authenticated',
          detail: 'Authentication credentials were not provided.',
          attr: null,
        },
      ],
    });
    expect(error.isUnauthenticated).toBe(true);
    expect(error.isForbidden).toBe(false);
  });

  it('falls back to a friendly message by status', () => {
    expect(new ApiError(0, []).message).toMatch(/Cannot reach the server/);
    expect(new ApiError(500, []).message).toMatch(/server had a problem/);
    expect(errorMessage(new Error('boom'))).toBe('boom');
  });

  it('parses a fetch Response', async () => {
    const response = new Response(
      JSON.stringify({ errors: [{ code: 'locked_out', detail: 'Too many attempts', attr: null }] }),
      {
        status: 429,
      },
    );
    const error = await ApiError.fromResponse(response);
    expect(error.status).toBe(429);
    expect(error.code).toBe('locked_out');
  });
});
