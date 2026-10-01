/**
 * AERION — BorderPage Video Playback & Error Classification Unit Tests
 * 
 * Verifies that the video error handling pipeline differentiates:
 * 1. True codec incompatibility (MEDIA_ERR_SRC_NOT_SUPPORTED with HTTP 200/206)
 * 2. Authentication / Authorization failures (HTTP 401 / 403)
 * 3. Missing storage artifacts (HTTP 404)
 * 4. Network and server errors (MEDIA_ERR_NETWORK, HTTP 5xx)
 * 5. Video decoding corruption (MEDIA_ERR_DECODE)
 * 6. User / client aborts (MEDIA_ERR_ABORTED)
 *
 * Prevents incorrectly labeling every failure as a codec limitation.
 */

import { classifyVideoError } from '../BorderPage';

// Mock MediaError constructor for test environments without browser DOM
class MockMediaError implements MediaError {
  readonly code: number;
  readonly message: string;
  readonly MEDIA_ERR_ABORTED = 1;
  readonly MEDIA_ERR_NETWORK = 2;
  readonly MEDIA_ERR_DECODE = 3;
  readonly MEDIA_ERR_SRC_NOT_SUPPORTED = 4;

  constructor(code: number, message: string = '') {
    this.code = code;
    this.message = message;
  }
}

export function runBorderPageVideoPlaybackTests(): { passed: number; failed: number } {
  let passed = 0;
  let failed = 0;

  function assert(condition: boolean, testName: string) {
    if (condition) {
      passed++;
    } else {
      failed++;
      console.error(`FAIL: ${testName}`);
    }
  }

  // 1. Codec Failure Distinction
  const codecErr = classifyVideoError(new MockMediaError(4), 200, 'mp4v');
  assert(codecErr.type === 'codec', 'Code 4 with HTTP 200 must be classified as codec incompatibility');
  assert(codecErr.title === 'Unsupported Video Codec', 'Codec failure title must reflect unsupported codec');
  assert(codecErr.message.includes('mp4v'), 'Codec error message must report specific codec');
  assert(codecErr.canRetry === false, 'Codec error should not suggest immediate retry');

  // 2. Authentication Failure Distinction (HTTP 401)
  const auth401Err = classifyVideoError(new MockMediaError(4), 401, 'avc1');
  assert(auth401Err.type === 'auth', 'HTTP 401 must be classified as auth failure, NOT codec failure');
  assert(auth401Err.title.includes('Authentication'), 'Auth 401 title must mention authentication');
  assert(auth401Err.canRetry === true, 'Auth failure should allow retry after login');

  // 3. Authorization Failure Distinction (HTTP 403)
  const auth403Err = classifyVideoError(new MockMediaError(4), 403, 'avc1');
  assert(auth403Err.type === 'auth', 'HTTP 403 must be classified as auth failure, NOT codec failure');
  assert(auth403Err.message.includes('permission'), 'Auth 403 message must mention permission denied');

  // 4. Missing Artifact Distinction (HTTP 404)
  const notFoundErr = classifyVideoError(new MockMediaError(4), 404, 'avc1');
  assert(notFoundErr.type === 'not_found', 'HTTP 404 must be classified as not_found, NOT codec failure');
  assert(notFoundErr.title === 'Evidence Artifact Not Found', 'HTTP 404 title must be artifact not found');
  assert(notFoundErr.canRetry === false, 'Missing artifact cannot be retried without re-generation');

  // 5. Network Error Distinction (MEDIA_ERR_NETWORK = 2)
  const networkErr = classifyVideoError(new MockMediaError(2), undefined, 'avc1');
  assert(networkErr.type === 'network', 'MediaError code 2 must be classified as network failure');
  assert(networkErr.title === 'Network Transfer Error', 'Network title must reflect network error');
  assert(networkErr.canRetry === true, 'Network errors should permit retry');

  // 6. Server 500 Error Distinction
  const server500Err = classifyVideoError(new MockMediaError(4), 500, 'avc1');
  assert(server500Err.type === 'network', 'HTTP 500 must be classified as network/server error');
  assert(server500Err.title === 'Server Error', 'HTTP 500 title must reflect server error');

  // 7. Video Decode Corruption Distinction (MEDIA_ERR_DECODE = 3)
  const decodeErr = classifyVideoError(new MockMediaError(3), 200, 'avc1');
  assert(decodeErr.type === 'decode', 'MediaError code 3 must be classified as decode failure');
  assert(decodeErr.title === 'Video Decode Error', 'Decode error title must reflect decode error');

  // 8. Video Aborted Distinction (MEDIA_ERR_ABORTED = 1)
  const abortErr = classifyVideoError(new MockMediaError(1), 200, 'avc1');
  assert(abortErr.type === 'aborted', 'MediaError code 1 must be classified as playback aborted');

  return { passed, failed };
}

// Auto-run if executed directly in test runner or Node
if (typeof process !== 'undefined' && process.env?.NODE_ENV === 'test') {
  const res = runBorderPageVideoPlaybackTests();
  if (res.failed > 0) {
    throw new Error(`BorderPage video playback tests failed: ${res.failed} failures`);
  }
}
