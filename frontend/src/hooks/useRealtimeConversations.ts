import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from './useWebSocket';
import { validateAndSanitizeMessage, webSocketMessageSchema, conversationIdSchema, isValidUUID } from '@/lib/validation';

interface Message {
  id: string;
  content: string;
  timestamp: string;
  sender: 'customer' | 'ai' | 'agent';
  channel?: string;
}

interface Chat {
  id: string;
  customerName: string;
  customerAvatar?: string;
  lastMessage: string;
  timestamp: string;
  channel: 'whatsapp' | 'instagram' | 'facebook' | 'widget';
  status: 'ai' | 'human' | 'pending' | 'closed';
  unreadCount: number;
  isActive: boolean;
}

interface UseRealtimeConversationsReturn {
  chats: Chat[];
  messages: { [chatId: string]: Message[] };
  isConnected: boolean;
  sendMessage: (chatId: string, content: string) => void;
  transferToHuman: (chatId: string) => void;
  refreshConversations: () => void;
  fetchMessages: (conversationId: string | number) => void;
  markAsRead: (chatId: string) => void;
}

export const useRealtimeConversations = (): UseRealtimeConversationsReturn => {
  const [chats, setChats] = useState<Chat[]>([]);
  const [messages, setMessages] = useState<{ [chatId: string]: Message[] }>({});
  
  const { isConnected, sendMessage: wsSendMessage, subscribe } = useWebSocket('wss://atendimento.pluggerbi.com/ws');

  // Subscribe to WebSocket messages
  useEffect(() => {
    const unsubscribe = subscribe((message) => {
      console.log('🔥 WEBSOCKET MESSAGE RECEIVED:', message.type, message);
      
      switch (message.type) {
        case 'new_message':
          console.log('📩 Handling new_message event');
          handleNewMessage(message.data);
          break;
        case 'subscription_updated':
          console.log('📊 Handling subscription_updated event');
          handleSubscriptionUpdate(message.data);
          break;
        case 'messages_response':
          console.log('💬 Handling messages_response event');
          handleMessagesResponse(message);
          break;
        case 'connection_confirmed':
          console.log('✅ Connection confirmed');
          break;
        case 'pong':
          console.log('🏓 Pong received');
          break;
        default:
          console.log('❓ Unknown message type:', message.type);
          break;
      }
    });

    return unsubscribe;
  }, [subscribe]);

  const handleNewMessage = useCallback((messageData: any) => {
    console.log('🔔 NEW MESSAGE RECEIVED:', messageData);
    
    if (!messageData) {
      console.log('❌ No message data received');
      return;
    }

    // Extract data - note that content could be in different fields
    const conversation_id = messageData.conversation_id;
    const message_id = messageData.id || messageData.message_id;
    const content = messageData.message_text || messageData.content || '';
    const sender = messageData.sender || 'customer';
    const timestamp = messageData.timestamp;
    const channel = messageData.channel;
    
    console.log('📍 Processing new message for conversation:', conversation_id);
    console.log('💬 Message details:', { message_id, content, sender, timestamp });

    // Add new message to the messages state with force update
    setMessages(prev => {
      const currentMessages = prev[conversation_id] || [];
      const newMessage = {
        id: message_id || `msg_${Date.now()}`,
        content: content,
        sender: sender === 'user' ? 'customer' : sender, // Map 'user' to 'customer'
        timestamp: timestamp ? new Date(timestamp).toLocaleDateString('pt-BR', { 
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit', 
          minute: '2-digit' 
        }) : new Date().toLocaleDateString('pt-BR', { 
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit', 
          minute: '2-digit' 
        }),
        channel
      };
      
      console.log('🔄 Adding message to conversation:', conversation_id, newMessage);
      console.log('📚 Current messages count:', currentMessages.length);
      
      const updatedMessages = {
        ...prev,
        [conversation_id]: [...currentMessages, newMessage]
      };
      
      console.log('📝 Updated messages state:', updatedMessages[conversation_id]);
      return updatedMessages;
    });

    // Update chat list with new last message
    setChats(prev => {
      const updatedChats = prev.map(chat => {
        if (chat.id === conversation_id) {
          console.log('🔄 Updating chat:', chat.id, 'with new message');
          return {
            ...chat,
            lastMessage: content,
            timestamp: timestamp ? new Date(timestamp).toLocaleDateString('pt-BR', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit'
            }) : new Date().toLocaleDateString('pt-BR', {
              day: '2-digit',
              month: '2-digit', 
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit'
            }),
            unreadCount: chat.unreadCount + 1,
            status: sender === 'customer' || sender === 'user' ? 'pending' : chat.status
          };
        }
        return chat;
      });
      
      console.log('💼 Updated chats with new message');
      return updatedChats;
    });
  }, []);

  const handleSubscriptionUpdate = useCallback((data: any) => {
    console.log('Processing subscription update:', data);
    
    if (data.conversations) {
      // Log each conversation to see channel data
      data.conversations.forEach((conv: any, index: number) => {
        console.log(`📋 CONVERSA ${index + 1}:`, {
          id: conv.id,
          channel: conv.channel,
          channel_type: conv.channel_type,
          contact_name: conv.contact_name,
          last_message: conv.last_message
        });
      });
      
      // Update chats list - mapping status_attendance to our status
      const updatedChats = data.conversations.map((conv: any) => ({
        id: conv.id,
        customerName: conv.contact_name || `Cliente ${conv.id}`,
        lastMessage: conv.last_message || 'Sem mensagens',
        timestamp: conv.last_message_time ? 
          new Date(conv.last_message_time).toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: '2-digit', 
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
          }) : '',
        channel: (() => {
          const channelValue = conv.channel_type || conv.channel;
          return (channelValue === 'whatsapp' || channelValue === 'instagram' || channelValue === 'facebook' || channelValue === 'widget') 
            ? channelValue : 'widget';
        })(),
        status: (() => {
          if (conv.status_attendance === 'bot') return 'ai';
          if (conv.status_attendance === 'human') return 'human';
          if (conv.status_attendance === 'pending') return 'pending';
          return 'pending';
        })(),
        unreadCount: conv.unread_count || 0,
        isActive: conv.status === 'active',
        botAgentName: conv.bot_agent_name || null
      }));
      
      setChats(updatedChats);
    }

    if (data.messages) {
      // Update messages for specific conversations
      const messagesByConversation: { [chatId: string]: Message[] } = {};
      
      data.messages.forEach((msg: any) => {
        const conversationId = msg.conversation_id;
        if (!messagesByConversation[conversationId]) {
          messagesByConversation[conversationId] = [];
        }
        
        messagesByConversation[conversationId].push({
          id: msg.id,
          content: msg.message_text || msg.content,
          sender: msg.sender === 'user' ? 'customer' : msg.sender,
          timestamp: new Date(msg.timestamp).toLocaleDateString('pt-BR', { 
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit', 
            minute: '2-digit' 
          }),
          channel: msg.channel
        });
      });

      setMessages(prev => ({
        ...prev,
        ...messagesByConversation
      }));
    }
  }, []);

  const handleMessagesResponse = useCallback((message: any) => {
    console.log('Processing messages response:', message);
    
    if (message.conversation_id && message.data && message.data.messages) {
      const conversationMessages = message.data.messages.map((msg: any) => ({
        id: msg.id,
        content: msg.message_text,
        sender: msg.sender === 'user' ? 'customer' : msg.sender,
        timestamp: new Date(msg.timestamp).toLocaleDateString('pt-BR', { 
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit', 
          minute: '2-digit' 
        }),
        channel: msg.channel
      }));

      console.log('📝 Setting messages for conversation:', message.conversation_id, conversationMessages);

      setMessages(prev => ({
        ...prev,
        [message.conversation_id]: conversationMessages
      }));
    }
  }, []);

  const sendMessage = useCallback((chatId: string, content: string) => {
    if (!isConnected) {
      console.warn('❌ WebSocket not connected. Cannot send message.');
      return;
    }

    if (!chatId) {
      console.warn('❌ No chat ID provided. Cannot send message.');
      return;
    }

    console.log('📤 SENDING MESSAGE to chat:', chatId, 'content:', content);
    console.log('🌐 WebSocket connection status:', isConnected);

    const messagePayload = {
      type: 'send_message',
      data: {
        conversation_id: chatId,
        content,
        sender: 'agent'
      }
    };

    console.log('📤 Sending message payload:', messagePayload);
    
    try {
      wsSendMessage(messagePayload);
      console.log('✅ Message sent successfully via WebSocket');
    } catch (error) {
      console.error('❌ Error sending message via WebSocket:', error);
      return;
    }
    
    // Optimistically add message to local state
    const tempMessage: Message = {
      id: `temp_${Date.now()}`,
      content,
      sender: 'agent',
      timestamp: new Date().toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric', 
        hour: '2-digit',
        minute: '2-digit'
      })
    };

    console.log('📝 Adding optimistic message to local state:', tempMessage);

    setMessages(prev => {
      const currentMessages = prev[chatId] || [];
      const updatedMessages = {
        ...prev,
        [chatId]: [...currentMessages, tempMessage]
      };
      console.log('📊 Updated messages state for chat:', chatId, updatedMessages[chatId]);
      return updatedMessages;
    });

    // Update chat last message
    setChats(prev => prev.map(chat => {
      if (chat.id === chatId) {
        console.log('📝 Updating chat last message for:', chatId);
        return {
          ...chat,
          lastMessage: content,
          timestamp: tempMessage.timestamp
        };
      }
      return chat;
    }));
  }, [isConnected, wsSendMessage]);

  const transferToHuman = useCallback((chatId: string) => {
    if (!isConnected) {
      console.warn('WebSocket not connected. Cannot transfer to human.');
      return;
    }

    const transferPayload = {
      type: 'transfer_to_human',
      data: {
        conversation_id: chatId
      }
    };

    wsSendMessage(transferPayload);
  }, [isConnected, wsSendMessage]);

  const fetchMessages = useCallback((conversationId: string | number) => {
    console.log('🔍 FETCH MESSAGES CALLED for conversation:', conversationId);
    console.log('🌐 WebSocket connected:', isConnected);
    
    // Convert to string if it's a number
    const conversationIdStr = String(conversationId);
    
    // Validate conversation ID
    try {
      conversationIdSchema.parse(conversationId);
    } catch (error) {
      console.error('Invalid conversation ID:', error);
      return;
    }
    
    if (!isConnected) {
      console.warn('❌ WebSocket not connected. Cannot fetch messages.');
      return;
    }

    console.log('🔍 FETCHING MESSAGES for conversation:', conversationIdStr);
    
    const fetchPayload = {
      type: 'get_messages',
      data: {
        conversation_id: conversationIdStr
      }
    };

    console.log('📤 Sending get_messages payload:', fetchPayload);
    wsSendMessage(fetchPayload);
  }, [isConnected, wsSendMessage]);

  const refreshConversations = useCallback(() => {
    if (!isConnected) {
      console.warn('WebSocket not connected. Cannot refresh conversations.');
      return;
    }

    const refreshPayload = {
      type: 'subscribe_conversations',
      data: {}
    };

    wsSendMessage(refreshPayload);
  }, [isConnected, wsSendMessage]);

  const markAsRead = useCallback((chatId: string) => {
    setChats(prev => prev.map(chat => {
      if (chat.id === chatId) {
        return {
          ...chat,
          unreadCount: 0
        };
      }
      return chat;
    }));
  }, []);

  return {
    chats,
    messages,
    isConnected,
    sendMessage,
    transferToHuman,
    refreshConversations,
    fetchMessages,
    markAsRead
  };
};