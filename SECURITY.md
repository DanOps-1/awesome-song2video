# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.5.x   | :white_check_mark: |
| < 0.5   | :x:                |

## Reporting a Vulnerability

We take the security of Song2Video seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### Please Do Not

- **Do not** open a public GitHub issue for security vulnerabilities
- **Do not** disclose the vulnerability publicly until we've had a chance to address it

### Please Do

1. **Email us** at 870657960@qq.com with:
   - A description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact
   - Any suggested fixes (if you have them)

2. **Use the subject line**: `[SECURITY] Brief description of the issue`

3. **Allow us time** to respond and fix the issue before public disclosure

### What to Expect

- **Acknowledgment**: We'll acknowledge receipt of your report within 48 hours
- **Updates**: We'll keep you informed about our progress
- **Timeline**: We aim to release a fix within 7-14 days for critical issues
- **Credit**: We'll credit you in the security advisory (unless you prefer to remain anonymous)

## Security Best Practices

When deploying Song2Video:

### API Keys and Secrets

- **Never commit** API keys or secrets to version control
- Use environment variables for all sensitive configuration
- Rotate API keys regularly
- Use different keys for development and production

### Network Security

- Run the application behind a reverse proxy (nginx, Caddy)
- Use HTTPS in production
- Implement rate limiting
- Use firewall rules to restrict access

### Database Security

- Use strong passwords for PostgreSQL
- Restrict database access to localhost or private network
- Enable SSL/TLS for database connections in production
- Regular backups

### Redis Security

- Set a strong Redis password (`requirepass`)
- Bind Redis to localhost only
- Disable dangerous commands (`CONFIG`, `FLUSHALL`, etc.)
- Use Redis ACLs if available

### Docker Security

- Don't run containers as root
- Use specific image tags, not `latest`
- Scan images for vulnerabilities
- Keep base images updated

### Input Validation

- The application validates file uploads (type, size)
- Lyrics input is sanitized
- API endpoints have rate limiting

### Dependencies

- We use Dependabot for automated dependency updates
- Security audits run on every PR
- Critical vulnerabilities are patched immediately

## Known Security Considerations

### External API Dependencies

Song2Video relies on external APIs:
- **TwelveLabs**: Video understanding API
- **DeepSeek**: LLM for query rewriting
- **Lyrics services**: QQ Music, NetEase, Kugou, LRCLIB

Ensure you:
- Use API keys with minimal required permissions
- Monitor API usage for anomalies
- Have rate limiting in place

### File Upload

- Maximum file size: 20MB (configurable)
- Allowed formats: MP3, WAV, FLAC, M4A, AAC
- Files are stored temporarily and cleaned up after processing
- No executable files are accepted

### FFmpeg Security

- FFmpeg is used for video processing
- Input validation prevents command injection
- Temporary files are isolated and cleaned up
- Consider running FFmpeg in a sandboxed environment

## Security Updates

Security updates are released as patch versions (e.g., 0.5.1, 0.5.2) and announced via:
- GitHub Security Advisories
- Release notes
- Email to security@example.com subscribers (if you want notifications)

## Compliance

This project:
- Uses CC BY-NC 4.0 license (non-commercial)
- Respects user privacy (no tracking, no analytics)
- Stores minimal user data
- Provides data export capabilities

## Questions?

If you have questions about security that aren't covered here, email us at 870657960@qq.com.

---

**Last Updated**: January 2026
