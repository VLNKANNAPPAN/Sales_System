# Redis executes each Lua script without running another command in between.
# Therefore GET + DECR + INCR below are one atomic state transition.
RESERVE_STOCK = """
local existing = redis.call('GET', KEYS[3])
if existing then
  return {2, existing}
end

local stock = redis.call('GET', KEYS[1])
if not stock or tonumber(stock) <= 0 then
  return {0, ''}
end

redis.call('DECR', KEYS[1])
local sequence = redis.call('INCR', KEYS[2])
local reservation_id = ARGV[1] .. sequence
redis.call('SET', KEYS[3], reservation_id, 'EX', ARGV[2])
return {1, reservation_id}
"""

# Uses Redis TIME, not an API-server clock: every service instance shares one clock.
TOKEN_BUCKET = """
local now = redis.call('TIME')
local now_ms = now[1] * 1000 + math.floor(now[2] / 1000)
local values = redis.call('HMGET', KEYS[1], 'tokens', 'last_ms')
local tokens = tonumber(values[1]) or tonumber(ARGV[1])
local last_ms = tonumber(values[2]) or now_ms
tokens = math.min(tonumber(ARGV[1]), tokens + (now_ms - last_ms) * tonumber(ARGV[2]) / 1000)
if tokens < 1 then
  redis.call('HMSET', KEYS[1], 'tokens', tokens, 'last_ms', now_ms)
  redis.call('PEXPIRE', KEYS[1], ARGV[3])
  return {0, tokens}
end
tokens = tokens - 1
redis.call('HMSET', KEYS[1], 'tokens', tokens, 'last_ms', now_ms)
redis.call('PEXPIRE', KEYS[1], ARGV[3])
return {1, tokens}
"""
