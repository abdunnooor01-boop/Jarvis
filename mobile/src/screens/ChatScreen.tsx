import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { useChatStore } from '../stores/chat';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

const ChatScreen = () => {
  const {
    conversations,
    currentConversationId,
    messages,
    isLoading,
    isStreaming,
    loadConversations,
    selectConversation,
    createConversation,
    sendMessage,
  } = useChatStore();
  const [input, setInput] = useState('');
  const [showSidebar, setShowSidebar] = useState(true);
  const flatListRef = useRef<FlatList>(null);
  const wsCleanup = useRef<(() => void) | null>(null);

  useEffect(() => {
    loadConversations();
    if (!currentConversationId) {
      createConversation('New Conversation');
    }
  }, []);

  useEffect(() => {
    if (flatListRef.current && currentConversationId) {
      const msgs = messages[currentConversationId] || [];
      if (msgs.length > 0) {
        setTimeout(() => {
          flatListRef.current?.scrollToEnd({ animated: true });
        }, 100);
      }
    }
  }, [messages, currentConversationId]);

  const currentMessages = currentConversationId
    ? messages[currentConversationId] || []
    : [];

  const handleSend = () => {
    if (!input.trim() || !currentConversationId) return;
    sendMessage(input.trim());
    setInput('');
  };

  const renderMessage = ({ item }: { item: any }) => (
    <View
      style={[
        styles.messageBubble,
        item.role === 'user' ? styles.userBubble : styles.assistantBubble,
      ]}
    >
      <Text
        style={[
          styles.messageText,
          item.role === 'user' ? styles.userText : styles.assistantText,
        ]}
      >
        {item.content}
      </Text>
    </View>
  );

  if (showSidebar) {
    return (
      <View style={styles.sidebar}>
        <View style={styles.sidebarHeader}>
          <Text style={styles.sidebarTitle}>Conversations</Text>
          <TouchableOpacity
            style={styles.newChatButton}
            onPress={() => createConversation()}
          >
            <Text style={styles.newChatButtonText}>+ New</Text>
          </TouchableOpacity>
        </View>
        <FlatList
          data={conversations}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[
                styles.conversationItem,
                currentConversationId === item.id && styles.conversationItemActive,
              ]}
              onPress={() => {
                selectConversation(item.id);
                setShowSidebar(false);
              }}
            >
              <Text
                style={[
                  styles.conversationTitle,
                  currentConversationId === item.id && styles.conversationTitleActive,
                ]}
                numberOfLines={1}
              >
                {item.title}
              </Text>
            </TouchableOpacity>
          )}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No conversations yet</Text>
          }
        />
        <TouchableOpacity
          style={styles.closeSidebar}
          onPress={() => setShowSidebar(false)}
        >
          <Text style={styles.closeSidebarText}>Close</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.menuButton}
          onPress={() => setShowSidebar(true)}
        >
          <Text style={styles.menuIcon}>☰</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>
          {conversations.find((c) => c.id === currentConversationId)?.title || 'Jarvis'}
        </Text>
        <View style={styles.headerRight} />
      </View>

      <FlatList
        ref={flatListRef}
        data={currentMessages}
        keyExtractor={(item) => item.id}
        renderItem={renderMessage}
        contentContainerStyle={styles.messagesContainer}
        ListEmptyComponent={
          !isLoading && !isStreaming ? (
            <View style={styles.emptyChat}>
              <Text style={styles.emptyChatTitle}>How can I help you today?</Text>
            </View>
          ) : null
        }
        ListFooterComponent={
          isStreaming ? (
            <View style={[styles.messageBubble, styles.assistantBubble]}>
              <ActivityIndicator size="small" color={colors.indigo[500]} />
              <Text style={[styles.messageText, styles.assistantText, { marginLeft: 8 }]}>
                Jarvis is thinking...
              </Text>
            </View>
          ) : null
        }
      />

      <View style={styles.inputContainer}>
        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="Type a message..."
            placeholderTextColor={colors.slate[400]}
            multiline
            onKeyPress={(e) => {
              if (e.nativeEvent.key === 'Enter' && Platform.OS === 'web') {
                handleSend();
              }
            }}
          />
          <TouchableOpacity
            style={[styles.sendButton, !input.trim() && styles.sendButtonDisabled]}
            onPress={handleSend}
            disabled={!input.trim()}
          >
            <Text style={styles.sendButtonText}>Send</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.disclaimer}>
          Jarvis can make mistakes. Check important info.
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.white,
  },
  sidebar: {
    flex: 1,
    backgroundColor: colors.slate[50],
    borderRightWidth: 1,
    borderRightColor: colors.slate[200],
  },
  sidebarHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate[200],
  },
  sidebarTitle: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.slate[900],
  },
  newChatButton: {
    backgroundColor: colors.indigo[600],
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  newChatButtonText: {
    color: colors.white,
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  conversationItem: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate[200],
  },
  conversationItemActive: {
    backgroundColor: colors.indigo[50],
  },
  conversationTitle: {
    fontSize: fontSize.md,
    color: colors.slate[700],
  },
  conversationTitleActive: {
    color: colors.indigo[700],
    fontWeight: '600',
  },
  emptyText: {
    textAlign: 'center',
    color: colors.slate[400],
    padding: spacing['2xl'],
    fontSize: fontSize.sm,
  },
  closeSidebar: {
    padding: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.slate[200],
    alignItems: 'center',
  },
  closeSidebarText: {
    color: colors.indigo[600],
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate[200],
    backgroundColor: colors.white,
  },
  menuButton: {
    padding: spacing.sm,
  },
  menuIcon: {
    fontSize: fontSize.xl,
    color: colors.slate[700],
  },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.slate[700],
  },
  headerRight: {
    width: 40,
  },
  messagesContainer: {
    padding: spacing.lg,
    flexGrow: 1,
  },
  messageBubble: {
    maxWidth: '80%',
    borderRadius: borderRadius['2xl'],
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  userBubble: {
    backgroundColor: colors.indigo[600],
    alignSelf: 'flex-end',
    borderTopRightRadius: 4,
  },
  assistantBubble: {
    backgroundColor: colors.slate[100],
    alignSelf: 'flex-start',
    borderTopLeftRadius: 4,
    flexDirection: 'row',
    alignItems: 'center',
  },
  messageText: {
    fontSize: fontSize.md,
    lineHeight: 20,
  },
  userText: {
    color: colors.white,
  },
  assistantText: {
    color: colors.slate[900],
  },
  emptyChat: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 100,
  },
  emptyChatTitle: {
    fontSize: fontSize.lg,
    color: colors.slate[400],
    fontWeight: '500',
  },
  inputContainer: {
    borderTopWidth: 1,
    borderTopColor: colors.slate[200],
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.white,
  },
  inputRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  input: {
    flex: 1,
    backgroundColor: colors.slate[100],
    borderRadius: borderRadius.xl,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.slate[900],
    maxHeight: 100,
  },
  sendButton: {
    backgroundColor: colors.indigo[600],
    borderRadius: borderRadius.xl,
    paddingHorizontal: spacing.lg,
    justifyContent: 'center',
  },
  sendButtonDisabled: {
    opacity: 0.5,
  },
  sendButtonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  disclaimer: {
    fontSize: fontSize.xs,
    color: colors.slate[400],
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});

export default ChatScreen;