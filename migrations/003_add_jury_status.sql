-- Migration: Add jury_status column to challenge_evaluations
-- Purpose: Track jury recruitment status to prevent race conditions
-- Status values: 'recruiting' (0-2 jury), 'finalizing' (3rd jury added, processing), 'locked' (complete)

ALTER TABLE challenge_evaluations 
ADD COLUMN jury_status TEXT DEFAULT 'recruiting';

-- Update existing records to 'recruiting'
UPDATE challenge_evaluations 
SET jury_status = 'recruiting' 
WHERE jury_status IS NULL;
