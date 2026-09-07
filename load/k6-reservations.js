import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const accepted = new Counter('reservations_accepted');
const soldOut = new Counter('reservations_sold_out');
const rateLimited = new Counter('reservations_rate_limited');
const unexpected = new Counter('reservations_unexpected');
const baseUrl = __ENV.BASE_URL || 'http://api:8000';

export const options = {
  scenarios: { flash_sale: { executor: 'shared-iterations', vus: 1000, iterations: 5000, maxDuration: '2m' } },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

export default function () {
  const key = `${__VU}-${__ITER}`;
  const response = http.post(`${baseUrl}/v1/items/flash-sale-item/reservations`, null, {
    headers: { 'Idempotency-Key': key, 'X-Client-ID': `load-client-${key}` },
  });
  if (response.status === 202) accepted.add(1);
  else if (response.status === 409) soldOut.add(1);
  else if (response.status === 429) rateLimited.add(1);
  else unexpected.add(1);
  check(response, { 'accepted or expected rejection': (r) => [202, 409, 429].includes(r.status) });
}

export function handleSummary(data) {
  return {
    stdout: JSON.stringify(data, null, 2),
    '/work/load-results/k6-summary.json': JSON.stringify(data, null, 2),
  };
}
