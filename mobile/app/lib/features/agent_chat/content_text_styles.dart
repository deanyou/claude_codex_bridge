import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

MarkdownStyleSheet cc_bridgeMarkdownStyleSheet(BuildContext context) {
  final theme = Theme.of(context);
  final colorScheme = theme.colorScheme;
  final textTheme = theme.textTheme;
  final codeBackground = colorScheme.tertiaryContainer.withValues(
    alpha: colorScheme.brightness == Brightness.dark ? 0.26 : 0.34,
  );
  final quoteBackground = colorScheme.secondaryContainer.withValues(
    alpha: colorScheme.brightness == Brightness.dark ? 0.20 : 0.28,
  );
  return MarkdownStyleSheet.fromTheme(theme).copyWith(
    a: textTheme.bodyMedium?.copyWith(
      color: colorScheme.secondary,
      decoration: TextDecoration.underline,
      decorationColor: colorScheme.secondary,
    ),
    p: textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface),
    h1: textTheme.headlineSmall?.copyWith(
      color: colorScheme.primary,
      fontWeight: FontWeight.w700,
    ),
    h2: textTheme.titleLarge?.copyWith(
      color: colorScheme.secondary,
      fontWeight: FontWeight.w700,
    ),
    h3: textTheme.titleMedium?.copyWith(
      color: colorScheme.tertiary,
      fontWeight: FontWeight.w700,
    ),
    strong: const TextStyle(fontWeight: FontWeight.w700),
    em: TextStyle(color: colorScheme.onSurfaceVariant),
    code: textTheme.bodyMedium?.copyWith(
      color: colorScheme.tertiary,
      fontFamily: 'monospace',
      backgroundColor: codeBackground,
    ),
    blockquote: textTheme.bodyMedium?.copyWith(
      color: colorScheme.onSurfaceVariant,
      fontStyle: FontStyle.italic,
    ),
    tableHead: textTheme.bodyMedium?.copyWith(
      color: colorScheme.primary,
      fontWeight: FontWeight.w700,
    ),
    tableBody: textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface),
    tableBorder: TableBorder.all(color: colorScheme.outlineVariant),
    blockSpacing: 10,
    codeblockPadding: const EdgeInsets.all(10),
    codeblockDecoration: BoxDecoration(
      color: codeBackground,
      border: Border.all(color: colorScheme.outlineVariant),
      borderRadius: BorderRadius.circular(6),
    ),
    blockquotePadding: const EdgeInsets.fromLTRB(12, 8, 10, 8),
    blockquoteDecoration: BoxDecoration(
      color: quoteBackground,
      border: Border(left: BorderSide(color: colorScheme.secondary, width: 4)),
      borderRadius: BorderRadius.circular(6),
    ),
  );
}
