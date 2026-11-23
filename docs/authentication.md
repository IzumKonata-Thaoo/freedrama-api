# Authentication

Two separate pieces: the **API token** and the **CDN cookie**.

## 1. Firebase anonymous sign-in

The app embeds a Google API key in `resources.arsc`:

```
AIzaSyCKncphbcD-b6vIRNByOnfnQlI1kqnNqNg
```

The Firebase project has **anonymous auth enabled**, so this returns a real ID
token without any account:

```http
POST https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=<API_KEY>
Content-Type: application/json

{"returnSecureToken": true}
```

```json
{
  "kind": "identitytoolkit#SignupNewUserResponse",
  "idToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6…",
  "refreshToken": "AMf-vBz…",
  "expiresIn": "3600",
  "localId": "…"
}
```

Refresh with:

```http
POST https://securetoken.googleapis.com/v1/token?key=<API_KEY>
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&refresh_token=<REFRESH_TOKEN>
```

`src/fdapi.py` caches the token in `src/firebase_token.json` and refreshes it
automatically.

## 2. The header scheme matters

| header | result |
|---|---|
| `Authorization: Bearer <firebase-id-token>` | **accepted** |
| `Authorization: jwt <firebase-id-token>` | `401 {"message":"Authentication failed: Invalid user"}` |
| no header | `401 "Login required to access this resource"` |

The Android app uses `jwt <token>` with a *server-issued* account token. A
Firebase ID token is not that token, but the API accepts it under `Bearer` — which
is why no app is needed.

App headers the API expects alongside it:

```http
User-Agent: free-drama-android/6.2.0
package-name: com.drama.free
build-number: 6020000
install-source: google_play
Accept-Language: en
```

## 3. CDN cookie

`media.cdn.kukufm.com` is behind CloudFront signed cookies and answers `403`
without them.

```http
GET /api/v1.0/utility/refresh-cloudfront-cookie/
Authorization: Bearer <token>
```

```json
{
  "cookies": {
    "CloudFront-Policy": "eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9tZWRpYS5jZG4ua3VrdWZtLmNvbS8qIiwiQ29uZGl0aW9uIjp7IkRhdGVMZXNzVGhhbiI6eyJBV1M6RXBvY2hUaW1lIjoxNzk1NDM1MTc4fX0sIkN1c3RvbURhdGEiOnsidXNlcl9pZCI6NDE1MTIzNzQ0fX1dfQ__",
    "CloudFront-Signature": "G9Ov~MP4II9lWPkXlpDH0J62bADdyR0p48aQ27Cq…",
    "CloudFront-Key-Pair-Id": "K2…"
  }
}
```

Send them as one `Cookie` header. ffmpeg:

```bash
ffmpeg -headers "Cookie: CloudFront-Policy=…; CloudFront-Signature=…; CloudFront-Key-Pair-Id=…" \
       -i "<hls_url>" -c copy out.mp4
```

The policy in the sample decodes to:

```json
{"Statement":[{"Resource":"https://media.cdn.kukufm.com/*",
  "Condition":{"DateLessThan":{"AWS:EpochTime":1795435178}},
  "CustomData":{"user_id":415123744}}]}
```

Bound to the user id, valid for about an hour.

## If you have a real account token

Put it in `src/token.txt`. `fdapi.py` prefers it over the anonymous one, exactly
the same way the app would.

## Failure modes

| Status | Meaning |
|---|---|
| `401 Login required` | no token, or scheme wrong |
| `401 Invalid user` | token present but not accepted (e.g. `jwt` with a Firebase token) |
| `403` on `media.cdn…` | missing or expired CloudFront cookie |
| `404 No matching url pattern` | route does not exist |
| `404 INVALID_GENRE` / `INVALID_CONTENTUNIT` | route exists, identifier wrong |
