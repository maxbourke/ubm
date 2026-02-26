# UBM Bookmark Categoriser

Automatically categorise your Twitter bookmarks using AI-powered taxonomy generation.

## Features

- **AI-Powered Taxonomy Generation**: Uses LLMs to analyse a sample of your bookmarks and generate a hierarchical category taxonomy
- **Intelligent Sampling**: Multiple sampling strategies (diverse, random) to ensure representative samples
- **Automatic Categorisation**: Assigns 1-3 relevant categories to each bookmark with confidence scores
- **Edge Case Detection**: Flags low-confidence assignments and suggests new categories
- **Hierarchical Categories**: Support for 3-level category trees (e.g., "AI > Machine Learning > Computer Vision")
- **Resume Support**: Interruption-safe processing that resumes from where it left off
- **Review Queue**: Track edge cases, low-confidence assignments, and taxonomy suggestions

## Quick Start

### 1. Set up API key

The categoriser uses OpenRouter to access LLM models:

```bash
export OPENROUTER_API_KEY="your-key-here"
```

Get a free API key at [openrouter.ai](https://openrouter.ai)

### 2. Generate taxonomy

```bash
# Generate taxonomy from 500 diverse bookmarks
ubm categorise init --sample-size 500 --strategy diverse

# Preview sample without generating (dry run)
ubm categorise init --sample-size 100 --dry-run

# Use specific model
ubm categorise init --model "anthropic/claude-3.5-sonnet" --yes
```

### 3. Categorise bookmarks

```bash
# Categorise all uncategorised bookmarks
ubm categorise run

# Categorise limited batch (useful for testing)
ubm categorise run --limit 100

# Categorise specific bookmarks by ID
ubm categorise run --ids 1234567890 9876543210

# Use specific model
ubm categorise run --model "anthropic/claude-3.5-sonnet"
```

### 4. Review results

```bash
# Show statistics
ubm categorise stats

# Display taxonomy tree
ubm categorise list

# Display with bookmark counts
ubm categorise list --counts

# Review edge cases and suggestions
ubm categorise review

# Filter review queue by type
ubm categorise review --type low_confidence
ubm categorise review --type taxonomy_suggestion
```

## Commands

### `ubm categorise init`

Generate taxonomy from sample bookmarks.

**Options:**
- `--sample-size N`: Number of bookmarks to sample (default: 500)
- `--strategy {diverse,random}`: Sampling strategy (default: diverse)
  - `diverse`: 20% top authors, 20% long-tail, 20% temporal, 40% random
  - `random`: Simple random sampling
- `--model MODEL`: LLM model to use (default: qwen-3.3-80b)
- `--dry-run`: Preview sample without generating taxonomy
- `--yes, -y`: Skip approval prompt

**Example:**
```bash
ubm categorise init --sample-size 200 --strategy diverse --yes
```

### `ubm categorise run`

Categorise bookmarks using the generated taxonomy.

**Options:**
- `--limit N`: Maximum bookmarks to categorise
- `--ids ID [ID ...]`: Specific bookmark IDs to categorise
- `--model MODEL`: LLM model to use (default: step-3.5-flash)

**Notes:**
- Resumes automatically if interrupted (Ctrl+C)
- Rate limited to 3 seconds between requests (safe for free tier)
- Shows progress updates every 10 bookmarks
- Estimated time: ~6 seconds per bookmark

**Example:**
```bash
# Test with small batch
ubm categorise run --limit 50

# Full run (can take 20-25 hours for 15K bookmarks)
ubm categorise run
```

### `ubm categorise stats`

Show categorisation statistics.

**Output:**
- Total bookmarks (categorised, needs review, pending)
- Number of categories
- Average confidence score
- Items needing review

### `ubm categorise list`

Display taxonomy tree.

**Options:**
- `--counts`: Show bookmark counts per category

**Example:**
```bash
ubm categorise list --counts
```

### `ubm categorise review`

Review edge cases and suggestions.

**Options:**
- `--type {low_confidence,taxonomy_suggestion,error}`: Filter by event type
- `--limit N`: Maximum items to show (default: 50)

**Example:**
```bash
# See all review items
ubm categorise review

# See only low-confidence assignments
ubm categorise review --type low_confidence

# See suggested new categories
ubm categorise review --type taxonomy_suggestion
```

## Database Schema

The categoriser adds 5 new tables to the UBM database:

### `categories`
Hierarchical taxonomy structure with parent-child relationships.

### `bookmark_categories`
Many-to-many mapping between bookmarks and categories with confidence scores.

### `categorisation_state`
Processing status tracking (pending, categorised, needs_review).

### `categorisation_log`
Edge cases, low-confidence assignments, and taxonomy suggestions.

### `taxonomy_history`
Audit trail of taxonomy generation and modifications.

## Sampling Strategies

### Diverse (Recommended)
- 20% from top authors (most bookmarked)
- 20% from long-tail authors (1-2 bookmarks)
- 20% temporal diversity (spread across date range)
- 40% random

This ensures the taxonomy represents your full collection, not just popular topics.

### Random
Simple random sampling. Good for quick tests but may over-represent popular topics.

## Performance

- **Taxonomy generation**: ~30 seconds (one-time)
- **Single bookmark categorisation**: 5-8 seconds (3s rate limit + 2-5s API)
- **Full 15K collection**: 20-25 hours (can run overnight, resumable)

### Optimization Options

1. **Use faster/cheaper models**: Switch to `stepfun/step-3.5-flash:free` for categorisation
2. **Batch processing**: Modify to categorise 5-10 bookmarks per API call (reduces time to 3-5 hours)
3. **Paid tier**: Remove rate limiting for parallel requests (<2 hours for 15K)

## Tips

1. **Start with a small sample**: Use `--sample-size 100 --dry-run` to preview before generating
2. **Test categorisation**: Run `--limit 50` first to verify quality
3. **Review suggestions**: Check `ubm categorise review` for missing categories
4. **Run overnight**: Full categorisation takes 20+ hours but is resumable
5. **Adjust taxonomy**: Regenerate with different sample sizes if categories don't fit well

## Model Recommendations

### Taxonomy Generation
- **Best quality**: `anthropic/claude-3.5-sonnet` (paid)
- **Good balance**: `qwen/qwen-3.3-80b-instruct:free` (free)
- **Fast**: `meta-llama/llama-3.3-70b-instruct:free` (free)

### Categorisation
- **Best quality**: `anthropic/claude-3.5-sonnet` (paid)
- **Good balance**: `stepfun/step-3.5-flash:free` (free)
- **Fast**: Use same model as taxonomy for consistency

## Troubleshooting

### API Key Not Set
```
Error: OPENROUTER_API_KEY environment variable not set
```

**Solution**: Export your OpenRouter API key:
```bash
export OPENROUTER_API_KEY="your-key-here"
```

### Rate Limit Errors
```
Error: Rate limit exceeded
```

**Solution**: The tool has built-in rate limiting (3s between requests). If you still hit limits:
1. Wait a few minutes and resume
2. Reduce batch size with `--limit`
3. Upgrade to paid tier for higher limits

### No Taxonomy Found
```
Error: No taxonomy found. Run 'ubm categorise init' first.
```

**Solution**: Generate taxonomy before categorising:
```bash
ubm categorise init --sample-size 500 --yes
```

### Low Confidence Assignments

If many bookmarks have low confidence (<60%):
1. Check `ubm categorise review --type taxonomy_suggestion` for missing categories
2. Consider regenerating taxonomy with larger sample size
3. Manually add missing categories (future feature)

## Architecture

### Migration System
Database schema changes are versioned and applied automatically on first run after update.

### Sampling
Configurable sampling strategies registered in `SAMPLING_STRATEGIES` dict for easy extension.

### LLM Integration
OpenRouter-compatible client with retry logic, rate limiting, and error handling.

### Edge Case Handling
Three-pronged approach:
1. Always assign best-fit category (never skip)
2. Flag low confidence (<0.6) for review
3. Log LLM suggestions for new categories

### Resume Support
Implicit pending state: bookmarks without `categorisation_state` entries are pending.
Interruption-safe: each bookmark saved atomically before moving to next.

## Future Enhancements

- [ ] Manual taxonomy management (add/remove/rename categories)
- [ ] Re-categorisation with filters (`--confidence-below 0.6`)
- [ ] Batch categorisation (5-10 per API call)
- [ ] Category search (`ubm search --category "AI"`)
- [ ] Export taxonomy to JSON/YAML
- [ ] Import custom taxonomy
- [ ] Category merge/split tools
- [ ] Confidence threshold configuration
- [ ] Multi-model consensus (use multiple LLMs, take vote)

## See Also

- [README.md](README.md) - Main UBM documentation
- [ROADMAP.md](ROADMAP.md) - Project roadmap
- [OpenRouter Docs](https://openrouter.ai/docs) - LLM API documentation
