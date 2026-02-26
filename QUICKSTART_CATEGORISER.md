# UBM Categoriser Quick Start

Get your 15K+ Twitter bookmarks categorised with AI in just a few commands.

## Setup (One-Time)

```bash
# 1. Set your OpenRouter API key (get free key at openrouter.ai)
export OPENROUTER_API_KEY="sk-or-v1-..."

# 2. Add to your shell profile for persistence
echo 'export OPENROUTER_API_KEY="sk-or-v1-..."' >> ~/.zshrc
source ~/.zshrc
```

## Usage (4 Steps)

### Step 1: Generate Taxonomy (30 seconds)

```bash
# Generate from 500 diverse bookmarks (recommended)
ubm categorise init --sample-size 500 --yes
```

This creates 15-40 hierarchical categories based on your actual bookmark content.

### Step 2: Test (5 minutes)

```bash
# Categorise first 50 bookmarks to verify quality
ubm categorise run --limit 50
```

Check results:
```bash
ubm categorise stats    # See statistics
ubm categorise list     # View taxonomy tree
```

### Step 3: Full Run (Overnight)

```bash
# Categorise all bookmarks (20-25 hours, resumable)
ubm categorise run
```

**Note**: You can interrupt (Ctrl+C) and resume anytime. Progress is saved after each bookmark.

### Step 4: Review & Refine

```bash
# Check statistics
ubm categorise stats

# Review suggestions for missing categories
ubm categorise review --type taxonomy_suggestion

# See low-confidence assignments
ubm categorise review --type low_confidence
```

## Common Tasks

### View Categorised Bookmarks

```bash
# Show specific bookmark with categories
ubm show 1234567890123456789

# Search and show (IDs displayed by default)
ubm search "AI" --limit 20
```

### Check Progress

```bash
# Quick stats
ubm categorise stats

# Taxonomy with bookmark counts
ubm categorise list --counts
```

### Resume Interrupted Run

```bash
# Just run again - picks up where it left off
ubm categorise run
```

## Tips

1. **Start small**: Test with `--limit 50` first to verify quality
2. **Run overnight**: Full categorisation takes 20-25 hours but is hands-off
3. **Check suggestions**: Review queue often has good ideas for missing categories
4. **Re-generate if needed**: If taxonomy doesn't fit, regenerate with larger sample
5. **Use faster model for testing**: Add `--model "stepfun/step-3.5-flash:free"` for quicker testing

## Models

### For Taxonomy Generation (init)
- **Best**: `anthropic/claude-3.5-sonnet` (paid, better quality)
- **Good**: Default free model (good enough for most cases)

### For Categorisation (run)
- **Best**: `anthropic/claude-3.5-sonnet` (paid, highest accuracy)
- **Fast**: `stepfun/step-3.5-flash:free` (free, 82% avg confidence observed)
- **Default**: Automatic selection

## Troubleshooting

### "OPENROUTER_API_KEY not set"
```bash
export OPENROUTER_API_KEY="your-key-here"
```

### "Rate limit exceeded"
Just wait 1-2 minutes and resume. Built-in rate limiting usually prevents this.

### "No taxonomy found"
Run `ubm categorise init` first to generate categories.

### Low confidence results
1. Check `ubm categorise review --type taxonomy_suggestion`
2. Consider regenerating with `--sample-size 1000`
3. May need to manually add missing categories (future feature)

## Full Documentation

- **Complete guide**: [CATEGORISER.md](CATEGORISER.md)
- **Implementation details**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **Main README**: [README.md](README.md)

## Example Session

```bash
# Setup
export OPENROUTER_API_KEY="sk-or-v1-..."

# Generate taxonomy (30s)
ubm categorise init --sample-size 500 --yes

# Test batch (5min)
ubm categorise run --limit 50

# Check results
ubm categorise stats
ubm categorise list --counts

# If satisfied, run full categorisation (overnight)
ubm categorise run

# Next morning, check progress
ubm categorise stats
# Output: Categorised: 15,552 (100.0%)

# Review any edge cases
ubm categorise review
```

## Cost Estimate

**Free Tier (OpenRouter)**:
- Taxonomy generation: Free
- Categorisation: Free (step-3.5-flash model)
- Rate: ~20 requests/min
- Total time: 20-25 hours
- Total cost: $0

**Paid Models (Optional)**:
- Claude 3.5 Sonnet: ~$0.50-1.00 for 15K bookmarks
- Faster, higher quality
- Can finish in 2-3 hours with parallelisation

## What You Get

After categorisation:
- ✓ 15-40 hierarchical categories
- ✓ Each bookmark has 1-3 relevant categories
- ✓ Confidence scores (80-95% typical)
- ✓ Categories shown in `ubm show` output
- ✓ Ready for future category-based search (coming soon)

## Next Features (Coming Soon)

- Category-based search: `ubm search "AI" --category "Machine Learning"`
- Manual taxonomy management: Add/remove/rename categories
- Re-categorisation: Fix low-confidence assignments
- Batch processing: 5x faster categorisation
