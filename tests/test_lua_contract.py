from app.lua import RESERVE_STOCK, TOKEN_BUCKET


def test_reservation_script_checks_idempotency_before_stock_and_decrements_once():
    assert RESERVE_STOCK.index("local existing") < RESERVE_STOCK.index("local stock")
    assert RESERVE_STOCK.count("DECR") == 1
    assert "INCR" in RESERVE_STOCK


def test_rate_limiter_uses_redis_time_and_bounds_tokens():
    assert "redis.call('TIME')" in TOKEN_BUCKET
    assert "math.min" in TOKEN_BUCKET
