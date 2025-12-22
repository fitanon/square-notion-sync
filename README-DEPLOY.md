## Deployment & Notes

Short checklist for deploying the static site components or using this starter in a hosted environment:

- Do NOT commit `.env` or any secrets. Use platform environment variables (Vercel, Netlify, Heroku) for production tokens.
- For Vercel: add the environment variables under Project Settings → Environment Variables. Deploy preview will pick them up.
- For CI: store secrets in your CI provider's secrets store and inject them at build/runtime.

Square sandbox testing
- Use `SQUARE_ENV=sandbox` and `SQUARE_SANDBOX_ACCESS_TOKEN` for testing.

Revoke tokens if they leak. Rotate credentials if you ever commit them.
