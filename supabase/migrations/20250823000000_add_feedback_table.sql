-- Create feedback table for tracking user feedback on DAO proposals
create table if not exists public.feedback (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now() not null,
  updated_at timestamptz default now() not null,
  
  -- Core identifiers
  profile_id uuid references public.profiles(id) not null,
  dao_id uuid references public.daos(id),
  proposal_id uuid references public.proposals(id) not null,
  
  -- Feedback data
  is_like boolean not null, -- True for like, False for dislike
  reasoning text -- Optional text explaining the feedback
);

-- Add indexes for common queries
create index if not exists idx_feedback_proposal_id on public.feedback(proposal_id);
create index if not exists idx_feedback_profile_id on public.feedback(profile_id);
create index if not exists idx_feedback_dao_id on public.feedback(dao_id);
create index if not exists idx_feedback_is_like on public.feedback(is_like);
create index if not exists idx_feedback_created_at on public.feedback(created_at);

-- Composite index for common query patterns
create index if not exists idx_feedback_proposal_profile on public.feedback(proposal_id, profile_id);

-- Add updated_at trigger (reuse existing function)
create trigger handle_feedback_updated_at
  before update on public.feedback
  for each row
  execute function public.handle_updated_at();

-- Add row level security (RLS)
alter table public.feedback enable row level security;

-- Create policy for authenticated users to read feedback
create policy "Users can view feedback" on public.feedback
  for select using (auth.role() = 'authenticated');

-- Create policy for users to insert feedback for their own profiles
create policy "Users can insert feedback for their profiles" on public.feedback
  for insert with check (
    auth.uid() = profile_id
  );

-- Create policy for users to update their own feedback
create policy "Users can update their own feedback" on public.feedback
  for update using (
    auth.uid() = profile_id
  );

-- Create policy for users to delete their own feedback
create policy "Users can delete their own feedback" on public.feedback
  for delete using (
    auth.uid() = profile_id
  );

-- Add unique constraint to prevent duplicate feedback from same user on same proposal
alter table public.feedback add constraint unique_profile_proposal_feedback 
  unique (profile_id, proposal_id);

-- Add comments for documentation
comment on table public.feedback is 'Tracks user feedback (likes/dislikes) on DAO proposals';
comment on column public.feedback.profile_id is 'Reference to the user profile that submitted the feedback';
comment on column public.feedback.dao_id is 'Reference to the DAO containing the proposal';
comment on column public.feedback.proposal_id is 'Reference to the proposal being rated';
comment on column public.feedback.is_like is 'True for like/positive feedback, False for dislike/negative feedback';
comment on column public.feedback.reasoning is 'Optional text explaining the reason for the feedback';