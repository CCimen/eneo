import { browser } from "$app/environment";
import { PAGINATION } from "$lib/core/constants";
import { createAsyncState } from "$lib/core/helpers/createAsyncState.svelte";
import { createClassContext } from "$lib/core/helpers/createClassContext";
import { waitFor } from "$lib/core/waitFor";
import {
  type ConversationSparse,
  type Assistant,
  type Conversation,
  type GroupChat,
  type Intric,
  type Paginated,
  type UploadedFile,
  type ConversationMessage,
  IntricError,
  type ConversationTools
} from "@intric/intric-js";

export type ChatPartner = GroupChat | Assistant;

export class ChatService {
  #chatPartner = $state<ChatPartner>() as ChatPartner; // Needs typecast to get rid of undefined
  partner = $derived(this.#chatPartner);
  #intric: Intric;
  currentConversation = $state<Conversation>(emptyConversation());
  totalConversations = $state<number>(0);
  loadedConversations = $state<ConversationSparse[]>([]);
  hasMoreConversations = $derived(this.loadedConversations.length < this.totalConversations);
  #nextCursor = $state<string | null>(null);

  // Deep Research mode state
  researchMode = $state<{
    active: boolean;
    selectedMode?: 'quick' | 'standard' | 'deep';
    placeholder?: string;
  }>({ active: false });

  constructor(data: Parameters<typeof this.init>[0]) {
    this.#intric = data.intric;
    this.init(data);
  }

  init(data: {
    intric: Intric;
    chatPartner: ChatPartner;
    initialConversation?: Promise<Conversation | null> | Conversation | null;
    initialHistory?: Promise<Paginated<ConversationSparse>> | Paginated<ConversationSparse>;
  }) {
    this.#chatPartner = data.chatPartner;

    waitFor(data.initialHistory, {
      onLoaded: (initialHistory) => {
        this.loadedConversations = initialHistory.items;
        this.totalConversations = initialHistory.total_count;
        this.#nextCursor = initialHistory.next_cursor ?? null;
      }
    });

    waitFor(data.initialConversation, {
      onLoaded: (initialConversation) => {
        this.currentConversation = initialConversation;
      },
      onNull: () => {
        this.currentConversation = emptyConversation();
      }
    });
  }

  newConversation() {
    this.currentConversation = emptyConversation();
  }

  async loadConversations(args?: { limit?: number; reset?: boolean }) {
    try {
      if (args?.reset) {
        this.#nextCursor = null;
      }
      const response = await this.#intric.conversations.list({
        chatPartner: this.#chatPartner,
        pagination: {
          limit: args?.limit ?? PAGINATION.PAGE_SIZE,
          cursor: this.#nextCursor ?? undefined
        }
      });

      if (args?.reset) {
        this.loadedConversations = response.items;
      } else {
        this.loadedConversations.push(...response.items);
      }

      this.#nextCursor = response.next_cursor ?? null;
      this.totalConversations = response.total_count;
      return response;
    } catch (error) {
      console.error("Error loading pagination", error);
    }
  }

  async loadMoreConversations(args?: { limit?: number }) {
    return this.loadConversations(args);
  }

  async reloadHistory() {
    return this.loadConversations({ reset: true });
  }

  async deleteConversation(conversation: { id: string }) {
    try {
      await this.#intric.conversations.delete(conversation);
      this.loadedConversations = this.loadedConversations.filter(
        ({ id }) => id !== conversation.id
      );
      if (this.currentConversation?.id === conversation.id) {
        this.newConversation();
      }
    } catch (e) {
      if (browser) alert(`Error while deleting conversation with id ${conversation.id}`);
      console.error(e);
    }
  }

  async loadConversation(conversation: { id: string }) {
    try {
      const loaded = await this.#intric.conversations.get(conversation);
      this.currentConversation = loaded;
      return loaded;
    } catch (e) {
      if (browser) alert(`Error while loading conversation with id ${conversation.id}`);
      console.error(e);
    }
  }

  changeChatPartner(newPartner: ChatPartner) {
    const oldPartner = this.#chatPartner;
    this.#chatPartner = newPartner;

    if (oldPartner !== newPartner) {
      this.newConversation();
      this.reloadHistory();
    }
  }

  askQuestion = createAsyncState(
    async (
      question: string,
      attachments?: UploadedFile[],
      tools?: ConversationTools,
      useWebSearch?: boolean,
      abortController?: AbortController
    ) => {
      this.currentConversation.messages?.push(emptyMessage({ question }));

      const ensureCurrentSession = (event: { session_id: string }) => {
        if (event.session_id !== this.currentConversation.id) {
          abortController?.abort();
          console.error(`cancelled streaming answer as session ${event.session_id} was changed.`);
        }
      };

      try {
        let buffer = "";
        const ref =
          this.currentConversation.messages[this.currentConversation.messages?.length - 1];

        await this.#intric.conversations.ask({
          question,
          chatPartner: this.#chatPartner,
          conversation: { id: this.currentConversation.id },
          files: (attachments ?? []).map((fileRef) => ({ id: fileRef.id })),
          tools,
          abortController,
          useWebSearch,
          callbacks: {
            onFirstChunk: (chunk) => {
              Object.assign(ref, chunk);
              this.currentConversation.id = chunk.session_id;
              this.currentConversation.name = question;
            },
            onText: (text) => {
              ensureCurrentSession(text);
              if (text.answer.includes("<") || buffer) {
                buffer += text.answer;
                if (isNotInref(buffer) || isCompleteInref(buffer)) {
                  ref.answer += buffer;
                  buffer = "";
                }
              } else {
                ref.answer += text.answer;
              }
              ref.references = text.references;
            },
            onImage: (image) => {
              ensureCurrentSession(image);
              Object.assign(ref, image);
            },
            onIntricEvent: (event) => {
              ensureCurrentSession(event);
              if (event.intric_event_type === "generating_image") {
                ref.generated_files.push({ id: "", name: "", mimetype: "", size: 0 });
              }
            }
          }
        });
      } catch (error) {
        const streamAborted = error instanceof Error && error.message.includes("aborted");
        if (streamAborted) {
          // In that case nothing more to do, just return
          return;
        }

        let message = "We encountered an error processing your request.";
        if (error instanceof IntricError) {
          message += `\n\`\`\`\n${error.code}: "${error.getReadableMessage()}"\n\`\`\``;
        } else if (error instanceof Object && "message" in error && "name" in error) {
          message += `\n\`\`\`\n$"${error.name}: error.message}"\n\`\`\``;
        }

        this.currentConversation.messages[this.currentConversation.messages?.length - 1].answer =
          message;
        console.error(error);
      }

      this.reloadHistory();
    }
  );

  // Deep Research Methods
  activateResearchMode(mode?: 'quick' | 'standard' | 'deep') {
    this.researchMode = {
      active: true,
      selectedMode: mode,
      placeholder: mode 
        ? `Enter your research query (${mode} mode)...`
        : 'Enter your research query...'
    };
    
    // Research mode activated - ready for user input
  }

  deactivateResearchMode() {
    this.researchMode = { active: false };
  }

  async startResearch(query: string, mode: 'quick' | 'standard' | 'deep') {
    // Add research question to chat
    this.currentConversation.messages?.push({
      ...emptyMessage({ question: `🔍 **Research Request**: ${query}` }),
      research_type: 'research_request',
      research_mode: mode,
      research_query: query
    });

    // Add "generating plan" message
    this.currentConversation.messages?.push({
      ...emptyMessage({}),
      research_type: 'research_plan_generating',
      answer: '⏳ Generating research plan...'
    });

    this.deactivateResearchMode();

    try {
      // Call research API through SvelteKit proxy
      const response = await fetch('/api/research/sessions', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query,
          mode,
          assistant_id: this.#chatPartner.id,
          space_id: this.#chatPartner.space_id || null
        })
      });

      if (!response.ok) throw new Error('Failed to start research');

      const session = await response.json();
      console.log('🔍 ChatService: Session created, status:', session.status);

      // Store session info but DON'T change research_type yet
      const lastMessage = this.currentConversation.messages[this.currentConversation.messages?.length - 1];
      console.log('🔍 ChatService: Storing session info in message:', lastMessage);
      
      lastMessage.research_session = session;
      
      console.log('🔍 ChatService: Session info stored, starting plan polling');

      // Poll for plan (message is still research_plan_generating)
      this.pollForResearchPlan(session.id);

    } catch (error) {
      // Update last message with error
      const lastMessage = this.currentConversation.messages[this.currentConversation.messages?.length - 1];
      lastMessage.answer = `❌ Failed to start research: ${error instanceof Error ? error.message : 'Unknown error'}`;
    }
  }

  async pollForResearchPlan(sessionId: string) {
    console.log('🔍 ChatService: Starting to poll for research plan:', sessionId);
    
    const maxAttempts = 30; // 30 seconds
    let attempts = 0;

    const poll = async () => {
      try {
        attempts++;
        console.log(`🔍 ChatService: Polling attempt ${attempts}/${maxAttempts}`);
        
        const response = await fetch(`/api/research/sessions/${sessionId}/plan`);
        
        if (response.ok) {
          const plan = await response.json();
          console.log('🔍 ChatService: Plan retrieved successfully:', plan);
          
          // Find and update the "generating" message
          const messages = this.currentConversation.messages;
          console.log('🔍 ChatService: Looking for plan message in', messages?.length, 'messages');
          
          // Log all message types for debugging
          messages?.forEach((msg, index) => {
            console.log(`🔍 Message ${index}:`, msg.research_type, msg.answer?.slice(0, 30));
          });
          
          const planMessage = messages?.find(m => m.research_type === 'research_plan_generating');
          
          if (planMessage) {
            console.log('🔍 ChatService: Found plan message, updating...');
            planMessage.research_type = 'research_plan';
            planMessage.research_plan = plan;
            planMessage.research_session = { id: sessionId };
            planMessage.answer = '📋 Research plan ready for approval';
            console.log('🔍 ChatService: Plan message updated successfully');
          } else {
            console.error('🔍 ChatService: Could not find plan generating message to update');
            console.log('🔍 ChatService: Available research_types:', messages?.map(m => m.research_type).filter(Boolean));
          }
          
          return;
        } else if (response.status === 409) {
          // Plan not ready yet, continue polling
          console.log('🔍 ChatService: Plan not ready yet, continuing...');
        } else {
          throw new Error(`Failed to get plan: ${response.status}`);
        }
        
      } catch (err) {
        console.log(`🔍 ChatService: Poll error (attempt ${attempts}):`, err);
      }
      
      // Continue polling if not at max attempts
      if (attempts < maxAttempts) {
        setTimeout(poll, 1000);
      } else {
        console.error('🔍 ChatService: Plan polling timeout after 30 seconds');
        
        // Update message with timeout error
        const messages = this.currentConversation.messages;
        const planMessage = messages?.find(m => m.research_type === 'research_plan_generating');
        if (planMessage) {
          planMessage.answer = '❌ Failed to generate research plan - timeout after 30 seconds';
        }
      }
    };

    // Start polling
    setTimeout(poll, 1000); // Start after 1 second
  }

  async approveResearchPlan(sessionId: string) {
    console.log('🔍 ChatService: Approving research plan:', sessionId);

    // Immediately update UI to show progress (don't wait for approval API)
    const messages = this.currentConversation.messages;
    const planMessage = messages?.find(m => m.research_type === 'research_plan');

    if (planMessage) {
      console.log('🔍 ChatService: Found plan message, immediately converting to progress');
      planMessage.research_type = 'research_progress';
      planMessage.research_progress = {
        progress: 0,
        status: 'starting',
        current_step: 'Starting research execution...',
        sources_found: 0,
        branches_complete: 0,
        total_branches: 6
      };
      planMessage.answer = '⚡ Research execution started';
      console.log('🔍 ChatService: Plan message updated to progress type:', planMessage.research_type);

      // Start progress updates immediately with session mode
      const sessionMode = planMessage.research_session?.mode || 'standard';
      this.trackResearchProgress(sessionId, sessionMode);
    } else {
      console.error('🔍 ChatService: No plan message found to convert to progress!');
    }

    // Now call the approval API in the background (non-blocking)
    try {
      console.log('🔍 ChatService: Calling approval API in background...');

      // Don't await - let it run in background
      fetch(`/api/research/sessions/${sessionId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved: true })
      }).then(response => {
        if (!response.ok) {
          console.error('🔍 ChatService: Approval API failed:', response.status);
        } else {
          console.log('🔍 ChatService: Approval API succeeded');
          return response.json();
        }
      }).then(result => {
        if (result) {
          console.log('🔍 ChatService: Approval result:', result);
        }
      }).catch(error => {
        console.error('🔍 ChatService: Approval API error:', error);
      });

    } catch (error) {
      console.error('🔍 ChatService: Approval failed:', error);
      
      // Update plan message with error
      const messages = this.currentConversation.messages;
      const planMessage = messages?.find(m => m.research_type === 'research_plan');
      if (planMessage) {
        planMessage.answer = `❌ Failed to approve research: ${error instanceof Error ? error.message : 'Unknown error'}`;
      }
    }
  }

  async trackResearchProgress(sessionId: string, researchMode?: string) {
    console.log('🔍 ChatService: Starting progress tracking for:', sessionId, 'mode:', researchMode);

    // Poll for session status to know when research is complete
    let attempts = 0;
    const maxAttempts = 300; // 5 minutes max (300 * 1 second) - increased for deep research
    let lastStatus = '';

    const pollStatus = async () => {
      attempts++;

      try {
        const response = await fetch(`/api/research/sessions/${sessionId}`, {
          cache: 'no-store',
          headers: {
            'Cache-Control': 'no-cache'
          }
        });
        if (response.ok) {
          const session = await response.json();

          // Only log if status changed
          if (session.status !== lastStatus) {
            console.log(`🔍 ChatService: Session status changed (${attempts}/${maxAttempts}): ${lastStatus} -> ${session.status}`);
            lastStatus = session.status;
          }

          // Update progress message with current status
          const messages = this.currentConversation.messages;
          const progressMessage = messages?.find(m => m.research_type === 'research_progress');

          // Debug logging for status and progress
          if (attempts === 1 || attempts % 10 === 0) {
            console.log(`🔍 ChatService: Poll ${attempts} - Status: ${session.status}, Progress: ${session.progress_percentage}%`);
          }

          if (progressMessage && session.status) {
            // Handle different statuses
            if (session.status === 'completed') {
              // Research is done, fetch results immediately
              console.log('🔍 ChatService: Research completed, fetching results');
              await this.completeResearchWithResults(sessionId);
              return;
            } else if (session.status === 'failed') {
              // Research failed
              if (progressMessage) {
                progressMessage.research_type = 'research_failed';
                progressMessage.answer = '❌ Research failed. Please try again.';
                progressMessage.research_progress = {
                  status: 'failed',
                  error_message: 'Research execution failed',
                  progress: 0
                };
              }
              return;
            } else if (session.status === 'executing' || session.status === 'approved' || session.status === 'running') {
              console.log(`🔍 ChatService: Status is '${session.status}' - updating progress display`);
              // Use real progress data from backend
              if (progressMessage.research_progress) {
                // Log progress data for debugging
                if (session.progress_percentage > 0 || session.current_step || session.sources_found > 0) {
                  console.log('🔍 ChatService: Real progress data:', {
                    progress: session.progress_percentage,
                    step: session.current_step,
                    sources: session.sources_found,
                    branches: `${session.branches_complete}/${session.total_branches}`
                  });
                }

                // Use actual progress from backend if available
                if (session.progress_percentage !== undefined && session.progress_percentage !== null) {
                  console.log(`🔍 ChatService: Updating progress from ${progressMessage.research_progress.progress}% to ${session.progress_percentage}%`);
                  progressMessage.research_progress.progress = session.progress_percentage;
                }

                // Use actual current step from backend if available
                if (session.current_step) {
                  progressMessage.research_progress.current_step = session.current_step;

                  // Determine status from current step
                  if (session.current_step.toLowerCase().includes('synthesiz') ||
                      session.current_step.toLowerCase().includes('generat')) {
                    progressMessage.research_progress.status = 'synthesizing';
                  } else if (session.current_step.toLowerCase().includes('search') ||
                             session.current_step.toLowerCase().includes('analyz')) {
                    progressMessage.research_progress.status = 'searching';
                  } else {
                    progressMessage.research_progress.status = 'starting';
                  }
                }

                // Use actual sources found from backend
                if (session.sources_found !== undefined) {
                  progressMessage.research_progress.sources_found = session.sources_found;
                }

                // Use actual branch progress from backend
                if (session.branches_complete !== undefined) {
                  progressMessage.research_progress.branches_complete = session.branches_complete;
                }
                if (session.total_branches !== undefined) {
                  progressMessage.research_progress.total_branches = session.total_branches;
                }

                // Fallback to time-based estimation ONLY if backend provides no data at all
                // Note: 0% is a valid progress value, only use fallback if undefined/null
                if ((session.progress_percentage === undefined || session.progress_percentage === null) && !session.current_step) {
                  const elapsedSeconds = attempts;
                  const sessionMode = session.mode || researchMode || 'standard';
                  const expectedDuration = sessionMode === 'quick' ? 60 : sessionMode === 'standard' ? 180 : 300;
                  const estimatedProgress = Math.min(90, Math.floor((elapsedSeconds / expectedDuration) * 90));

                  console.log(`🔍 ChatService: No backend progress data, using time-based estimate: ${estimatedProgress}%`);
                  progressMessage.research_progress.progress = estimatedProgress;
                  progressMessage.research_progress.current_step = 'Research in progress...';
                  progressMessage.research_progress.status = elapsedSeconds < 10 ? 'starting' : 'searching';
                }
              }
            }
          }

          // Continue polling if not complete and haven't exceeded max attempts
          if (session.status !== 'completed' && session.status !== 'failed' && attempts < maxAttempts) {
            setTimeout(pollStatus, 1000); // Poll every second
          } else if (attempts >= maxAttempts) {
            console.error('🔍 ChatService: Progress tracking timeout');
            if (progressMessage) {
              progressMessage.research_type = 'research_failed';
              progressMessage.answer = '⏱️ Research timeout. Please try again.';
            }
          }
        }
      } catch (error) {
        console.error('🔍 ChatService: Error polling status:', error);
        if (attempts < maxAttempts) {
          setTimeout(pollStatus, 2000); // Retry after 2 seconds on error
        }
      }
    };

    // Start polling
    setTimeout(pollStatus, 1000);
  }

  async completeResearchWithResults(sessionId: string) {
    console.log('🔍 ChatService: Fetching research results:', sessionId);
    
    try {
      const response = await fetch(`/api/research/sessions/${sessionId}/results`);
      
      if (response.ok) {
        const results = await response.json();
        console.log('🔍 ChatService: Results retrieved:', results);

        // Find progress message and convert to results
        const messages = this.currentConversation.messages;
        const progressMessage = messages?.find(m => m.research_type === 'research_progress');
        
        if (progressMessage) {
          progressMessage.research_type = 'research_results';
          progressMessage.research_results = results;
          progressMessage.answer = '✅ Research completed successfully';
          console.log('🔍 ChatService: Progress message updated to results');
        }
      }
    } catch (error) {
      console.error('🔍 ChatService: Failed to get results:', error);
    }
  }
}

export const [getChatService, initChatService] = createClassContext("Chat service", ChatService);

function emptyMessage(partial?: Partial<ConversationMessage>): ConversationMessage {
  return {
    generated_files: [],
    question: "",
    answer: "",
    references: [],
    files: [],
    web_search_references: [],
    tools: {
      assistants: []
    },
    ...partial
  };
}

function emptyConversation(): Conversation {
  return {
    id: "",
    name: "New conversation",
    messages: []
  };
}

const couldBeInref = (buffer: string): boolean => {
  // We assume that "<" can be anywhere in the buffer, but that there can only be one
  return "<inref".startsWith(buffer.slice(buffer.indexOf("<"), 5));
};
const isNotInref = (buffer: string): boolean => !couldBeInref(buffer);
const isCompleteInref = (buffer: string): boolean => couldBeInref(buffer) && buffer.includes(">");
