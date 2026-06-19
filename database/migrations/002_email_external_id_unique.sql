-- Index unique pour éviter les doublons à la synchronisation IMAP

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_requests_external_id
    ON email_requests (external_id)
    WHERE external_id IS NOT NULL;
