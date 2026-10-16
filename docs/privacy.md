# Privacy

Tutoring boards may contain students' names and handwriting, and students are often minors.

- **The public demo is fictional.** The demo teacher, students, lessons and boards are synthetic
  (`api/app/seed.py`). Never seed or showcase real student data.
- **Accounts are isolated.** Teachers only see their own students and lessons. Students only see
  their own lessons.
- **Images are capability URLs.** Board images are served under random, unguessable file names.
  Anyone with the link can view the image, so don't share board image links publicly.
- **Third parties.** Board images and transcripts are sent to the Claude API for reconstruction
  and summaries. Recaps are sent through Telegram and/or Resend when those channels are enabled.
  Make sure students (or their parents) agree to this.
- **Deletion.** Deleting a board or lesson removes its images from disk.
- **Production secrets.** The API refuses to start in `ENVIRONMENT=production` with the default
  `JWT_SECRET`.
