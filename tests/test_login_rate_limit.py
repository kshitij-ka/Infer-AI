import fakeredis

from app.api.routes.auth import _build_login_rate_limit_key
from app.services.cache import is_rate_limited


def test_login_rate_limit_blocks_after_threshold(client, seed_user):
    """
    Repeated login attempts against the same username and client IP
    beyond the configured threshold get 429, regardless of whether
    the password is correct, so a brute force loop is blocked before
    it can guess the password.
    """
    seed_user(username="alice", password="password123")

    last_status = None
    for _ in range(15):
        response = client.post(
            "/auth/login",
            json={"username": "alice", "password": "wrong-password"},
        )
        last_status = response.status_code

    assert last_status == 429


def test_login_succeeds_under_rate_limit(client, seed_user):
    """A single correct login attempt succeeds normally."""
    seed_user(username="bob", password="password123")

    response = client.post(
        "/auth/login",
        json={"username": "bob", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_rate_limit_key_does_not_collide_across_username_ip_boundary():
    """
    Two different (username, ip) pairs that would have produced the
    identical literal string under a plain "login:{username}:{ip}"
    concatenation must not share a rate limit bucket. The colliding
    pair below is constructed from a victim logging in from an IPv6
    address (which itself contains colons) and a crafted username
    that ends with a colon, so that joining "crafted_username : ip"
    reassembles into the exact same character sequence as joining
    "victim_username : victim_ip", even though the two pairs are not
    the same username and not the same IP. Exhausting the crafted
    pair's quota must leave the victim's own bucket unaffected.
    """
    victim_username = "victim"
    victim_ip = "::1"

    crafted_username = "victim:"
    crafted_ip = ":1"

    old_scheme_attacker_key = f"login:{crafted_username}:{crafted_ip}"
    old_scheme_victim_key = f"login:{victim_username}:{victim_ip}"
    assert old_scheme_attacker_key == old_scheme_victim_key, (
        "test setup error: the crafted pair must reproduce the exact "
        "collision the old raw concatenation scheme was vulnerable to"
    )
    assert (crafted_username, crafted_ip) != (victim_username, victim_ip)

    attacker_key = _build_login_rate_limit_key(crafted_username, crafted_ip)
    victim_key = _build_login_rate_limit_key(victim_username, victim_ip)
    assert attacker_key != victim_key

    fake_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    limit = 10

    for _ in range(limit + 5):
        is_rate_limited(fake_redis, key=attacker_key, limit_per_minute=limit)

    assert is_rate_limited(fake_redis, key=victim_key, limit_per_minute=limit) is False
