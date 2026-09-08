from shawei.fetch.http_client import _decode_http_body


def test_gb2312_header_uses_gb18030_compatible_decoder() -> None:
    raw = "澳彩碼王".encode("gb18030")
    assert _decode_http_body(raw, charset="gb2312") == "澳彩碼王"
    assert _decode_http_body(raw, charset="gbk") == "澳彩碼王"
