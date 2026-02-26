"""Core categorisation logic with LLM integration."""

import json
import sqlite3
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import os


# LLM Configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Default models
# Taxonomy generation: Use Sonnet for quality (one-time, ~$0.02)
DEFAULT_TAXONOMY_MODEL = 'anthropic/claude-3.5-sonnet'
# Categorisation: Use Haiku for cost efficiency (~$0.10 for 15K bookmarks)
DEFAULT_CATEGORISATION_MODEL = 'anthropic/claude-3.5-haiku'

# Rate limiting
DEFAULT_RATE_LIMIT_DELAY = 3.0  # seconds between requests

# Confidence threshold for review
CONFIDENCE_THRESHOLD = 0.6


def log_llm_interaction(
    interaction_type: str,
    model: str,
    prompt: str,
    response: str,
    parsed_result: Any = None,
    error: str = None,
    bookmark_id: str = None,
    metadata: Dict = None
) -> None:
    """Log LLM interaction to JSONL file.

    Args:
        interaction_type: Type of interaction (e.g., 'taxonomy_generation', 'categorisation_ontology')
        model: Model identifier
        prompt: Input prompt
        response: Model response
        parsed_result: Parsed result object (will be converted to string)
        error: Error message if interaction failed
        bookmark_id: Bookmark ID if applicable
        metadata: Additional metadata dictionary
    """
    log_path = Path.home() / '.ubm' / 'llm_log.jsonl'
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log_entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'type': interaction_type,
        'model': model,
        'prompt': prompt,
        'response': response,
        'parsed': str(parsed_result) if parsed_result else None,
        'error': error,
        'bookmark_id': bookmark_id,
        'metadata': metadata or {}
    }

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry) + '\n')


def log_suggestions_to_file(bookmark_id: str, suggestions: List['CategorySuggestion']) -> None:
    """Append category suggestions to human-readable text log.

    Args:
        bookmark_id: Bookmark ID
        suggestions: List of CategorySuggestion objects
    """
    log_path = Path.home() / '.ubm' / 'suggestions.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_path, 'a', encoding='utf-8') as f:
        for sug in suggestions:
            f.write(f"{timestamp} | Bookmark: {bookmark_id} | {sug.name} ({sug.confidence:.2f})\n")


@dataclass
class Category:
    """Category data structure."""
    name: str
    parent: Optional[str]
    description: str
    level: int


@dataclass
class CategorySuggestion:
    """Suggested category with confidence score."""
    name: str
    confidence: float


@dataclass
class CategorisationResult:
    """Result of categorising a single bookmark."""
    categories: List[Tuple[int, float]]  # (category_id, confidence)
    suggestions: List[CategorySuggestion]  # Suggested new categories with confidence
    explanation: str


class LLMClient:
    """OpenRouter API client for LLM integration."""

    def __init__(self, api_key: str, rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY):
        """Initialise LLM client.

        Args:
            api_key: OpenRouter API key
            rate_limit_delay: Delay between requests in seconds
        """
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        log_type: str = None,
        bookmark_id: str = None
    ) -> str:
        """Call OpenRouter chat completion API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            log_type: Type of interaction for logging (e.g., 'taxonomy_generation')
            bookmark_id: Bookmark ID for logging (if applicable)

        Returns:
            Response content string

        Raises:
            RuntimeError: On API errors
        """
        prompt = messages[0]['content'] if messages else ''
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        # Build request
        data = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens
        }

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/yourusername/ubm',
            'X-Title': 'UBM Categoriser'
        }

        req = urllib.request.Request(
            OPENROUTER_API_URL,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        # Make request with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    self.last_request_time = time.time()
                    result = json.loads(response.read().decode('utf-8'))
                    response_text = result['choices'][0]['message']['content']

                    # Log successful interaction
                    if log_type:
                        log_llm_interaction(
                            interaction_type=log_type,
                            model=model,
                            prompt=prompt,
                            response=response_text,
                            bookmark_id=bookmark_id
                        )

                    return response_text

            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') if e.fp else ''

                if e.code == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5
                        time.sleep(wait_time)
                        continue
                    error_msg = f"Rate limit exceeded: {error_body}"
                    if log_type:
                        log_llm_interaction(
                            interaction_type=log_type,
                            model=model,
                            prompt=prompt,
                            response='',
                            error=error_msg,
                            bookmark_id=bookmark_id
                        )
                    raise RuntimeError(error_msg)

                elif e.code >= 500:  # Server error
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        time.sleep(wait_time)
                        continue
                    error_msg = f"Server error {e.code}: {error_body}"
                    if log_type:
                        log_llm_interaction(
                            interaction_type=log_type,
                            model=model,
                            prompt=prompt,
                            response='',
                            error=error_msg,
                            bookmark_id=bookmark_id
                        )
                    raise RuntimeError(error_msg)

                else:  # Client error (4xx)
                    error_msg = f"API error {e.code}: {error_body}"
                    if log_type:
                        log_llm_interaction(
                            interaction_type=log_type,
                            model=model,
                            prompt=prompt,
                            response='',
                            error=error_msg,
                            bookmark_id=bookmark_id
                        )
                    raise RuntimeError(error_msg)

            except urllib.error.URLError as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                error_msg = f"Network error: {e.reason}"
                if log_type:
                    log_llm_interaction(
                        interaction_type=log_type,
                        model=model,
                        prompt=prompt,
                        response='',
                        error=error_msg,
                        bookmark_id=bookmark_id
                    )
                raise RuntimeError(error_msg)

            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                if log_type:
                    log_llm_interaction(
                        interaction_type=log_type,
                        model=model,
                        prompt=prompt,
                        response='',
                        error=error_msg,
                        bookmark_id=bookmark_id
                    )
                raise RuntimeError(error_msg)

        error_msg = "Max retries exceeded"
        if log_type:
            log_llm_interaction(
                interaction_type=log_type,
                model=model,
                prompt=prompt,
                response='',
                error=error_msg,
                bookmark_id=bookmark_id
            )
        raise RuntimeError(error_msg)


# Sampling Strategies

def sample_bookmarks_diverse(conn: sqlite3.Connection, n: int) -> List[Dict]:
    """Sample bookmarks using diverse strategy.

    Strategy:
    - 20% from top authors (most bookmarked)
    - 20% from long-tail authors (1-2 bookmarks)
    - 20% temporal diversity (spread across date range)
    - 40% random

    Args:
        conn: Database connection
        n: Number of bookmarks to sample

    Returns:
        List of bookmark dictionaries
    """
    cursor = conn.cursor()
    bookmarks = []

    # Calculate split
    n_top = int(n * 0.2)
    n_longtail = int(n * 0.2)
    n_temporal = int(n * 0.2)
    n_random = n - n_top - n_longtail - n_temporal

    # 20% from top authors
    cursor.execute("""
        WITH author_counts AS (
            SELECT author_handle, COUNT(*) as count
            FROM bookmarks
            WHERE author_handle IS NOT NULL
            GROUP BY author_handle
            ORDER BY count DESC
            LIMIT 20
        )
        SELECT b.id, b.content, b.author_handle, b.created_at
        FROM bookmarks b
        INNER JOIN author_counts ac ON b.author_handle = ac.author_handle
        ORDER BY RANDOM()
        LIMIT ?
    """, (n_top,))
    bookmarks.extend([dict(row) for row in cursor.fetchall()])

    # 20% from long-tail authors
    cursor.execute("""
        WITH author_counts AS (
            SELECT author_handle, COUNT(*) as count
            FROM bookmarks
            WHERE author_handle IS NOT NULL
            GROUP BY author_handle
            HAVING count BETWEEN 1 AND 2
        )
        SELECT b.id, b.content, b.author_handle, b.created_at
        FROM bookmarks b
        INNER JOIN author_counts ac ON b.author_handle = ac.author_handle
        ORDER BY RANDOM()
        LIMIT ?
    """, (n_longtail,))
    bookmarks.extend([dict(row) for row in cursor.fetchall()])

    # 20% temporal diversity - stratified by year
    cursor.execute("""
        SELECT DISTINCT strftime('%Y', created_at) as year
        FROM bookmarks
        WHERE created_at IS NOT NULL
        ORDER BY year
    """)
    years = [row['year'] for row in cursor.fetchall()]

    if years:
        per_year = max(1, n_temporal // len(years))
        for year in years:
            cursor.execute("""
                SELECT id, content, author_handle, created_at
                FROM bookmarks
                WHERE strftime('%Y', created_at) = ?
                ORDER BY RANDOM()
                LIMIT ?
            """, (year, per_year))
            bookmarks.extend([dict(row) for row in cursor.fetchall()])

        # Trim to target count
        if len(bookmarks) > n_top + n_longtail + n_temporal:
            bookmarks = bookmarks[:n_top + n_longtail + n_temporal]

    # Fill remaining with random
    remaining = n - len(bookmarks)
    if remaining > 0:
        # Get IDs already sampled
        sampled_ids = [b['id'] for b in bookmarks]
        placeholders = ','.join('?' * len(sampled_ids))

        cursor.execute(f"""
            SELECT id, content, author_handle, created_at
            FROM bookmarks
            WHERE id NOT IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT ?
        """, (*sampled_ids, remaining))
        bookmarks.extend([dict(row) for row in cursor.fetchall()])

    return bookmarks


def sample_bookmarks_random(conn: sqlite3.Connection, n: int) -> List[Dict]:
    """Sample bookmarks randomly.

    Args:
        conn: Database connection
        n: Number of bookmarks to sample

    Returns:
        List of bookmark dictionaries
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, content, author_handle, created_at
        FROM bookmarks
        ORDER BY RANDOM()
        LIMIT ?
    """, (n,))

    return [dict(row) for row in cursor.fetchall()]


# Sampling strategy registry
SAMPLING_STRATEGIES = {
    'diverse': sample_bookmarks_diverse,
    'random': sample_bookmarks_random,
}


# Taxonomy Generation

def generate_taxonomy_prompt(bookmarks: List[Dict], sample_size: int) -> str:
    """Construct LLM prompt for taxonomy generation.

    Args:
        bookmarks: Sample bookmarks
        sample_size: Total sample size

    Returns:
        Formatted prompt string
    """
    # Format first 100 bookmarks in detail
    bookmark_lines = []
    for i, bm in enumerate(bookmarks[:100], 1):
        author = bm.get('author_handle', 'unknown')
        if not author.startswith('@'):
            author = f"@{author}"
        content = (bm.get('content') or '')[:200]  # Truncate long content
        bookmark_lines.append(f"{i}. {author}: {content}")

    bookmarks_text = '\n'.join(bookmark_lines)

    remaining = sample_size - 100
    remaining_text = f"\n\n...and {remaining} more bookmarks summarised above" if remaining > 0 else ""

    prompt = f"""You are an expert librarian and taxonomist. Analyse these {sample_size} Twitter bookmarks and design a hierarchical category taxonomy.

SAMPLE BOOKMARKS (first 100 of {sample_size}):
{bookmarks_text}{remaining_text}

CRITICAL REQUIREMENTS:
1. Create 20-50 categories total (including subcategories)
2. MUST use hierarchical structure with 2-3 levels - flat taxonomies are NOT acceptable
3. Use clear parent-child relationships - at least 60% of categories should have a parent
4. Categories should be mutually exclusive where possible, comprehensive, specific yet general
5. Consider the diverse topics: technology, business, culture, science, politics, etc.

HIERARCHY EXAMPLES:
- Technology > AI > LLMs (3 levels)
- Technology > Developer Tools (2 levels)
- Politics > Geopolitics > Foreign Policy (3 levels)
- Science > Research > Academia (3 levels)
- Economics > Finance > Trading (3 levels)

Think of this like Obsidian tags: #technology/ai/llms or #politics/geopolitics/conflicts

OUTPUT FORMAT (JSON):
{{
  "categories": [
    {{"name": "Technology", "parent": null, "description": "Technology and computing topics", "level": 0}},
    {{"name": "AI", "parent": "Technology", "description": "Artificial intelligence and machine learning", "level": 1}},
    {{"name": "LLMs", "parent": "AI", "description": "Large language models and applications", "level": 2}},
    {{"name": "Developer Tools", "parent": "Technology", "description": "Software development utilities", "level": 1}},
    {{"name": "Politics", "parent": null, "description": "Political topics and governance", "level": 0}},
    {{"name": "Geopolitics", "parent": "Politics", "description": "International relations and policy", "level": 1}},
    ...
  ]
}}

VALIDATION CHECKLIST:
- ✓ At least 4-8 top-level categories (level 0, parent: null)
- ✓ Most categories should be level 1 or 2 (children/grandchildren)
- ✓ Each parent name must match exactly when referenced
- ✓ Levels must be sequential (0 -> 1 -> 2, no jumps)

Respond ONLY with valid JSON. No explanations or markdown formatting."""

    return prompt


def parse_taxonomy_response(response: str) -> List[Category]:
    """Parse LLM response into Category objects.

    Args:
        response: JSON response from LLM

    Returns:
        List of Category objects

    Raises:
        ValueError: If response is invalid JSON or missing required fields
    """
    # Strip markdown code blocks if present
    response = response.strip()
    if response.startswith('```'):
        lines = response.split('\n')
        response = '\n'.join(lines[1:-1])  # Remove first and last lines

    try:
        data = json.loads(response)
        categories = []

        for cat_data in data.get('categories', []):
            category = Category(
                name=cat_data['name'],
                parent=cat_data.get('parent'),
                description=cat_data.get('description', ''),
                level=cat_data.get('level', 0)
            )
            categories.append(category)

        return categories

    except (json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Invalid taxonomy response: {e}")


def save_taxonomy(
    conn: sqlite3.Connection,
    categories: List[Category],
    sample_size: int,
    model: str
) -> None:
    """Save taxonomy to database.

    Inserts categories respecting hierarchy (parents before children).
    Logs to taxonomy_history.

    Args:
        conn: Database connection
        categories: List of Category objects
        sample_size: Sample size used for generation
        model: Model used for generation
    """
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    # Sort categories by level (parents first)
    categories_sorted = sorted(categories, key=lambda c: c.level)

    # Track name -> id mapping
    name_to_id = {}

    # Insert categories
    for category in categories_sorted:
        parent_id = None
        if category.parent:
            parent_id = name_to_id.get(category.parent)
            if parent_id is None:
                raise ValueError(f"Parent category not found: {category.parent}")

        cursor.execute("""
            INSERT INTO categories (name, parent_id, description, level, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (category.name, parent_id, category.description, category.level, now))

        name_to_id[category.name] = cursor.lastrowid

    # Log to taxonomy history
    cursor.execute("""
        INSERT INTO taxonomy_history (action, description, sample_size, model_used, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, ('generated', f'Generated {len(categories)} categories', sample_size, model, now))

    conn.commit()


# Bookmark Categorisation

def get_uncategorised_bookmarks(conn: sqlite3.Connection, limit: Optional[int] = None) -> List[str]:
    """Get IDs of bookmarks that need categorisation.

    Returns bookmarks without entries in categorisation_state (implicit pending).
    Results sorted by ID for deterministic ordering.

    Args:
        conn: Database connection
        limit: Maximum number of IDs to return (None for all)

    Returns:
        List of bookmark IDs
    """
    cursor = conn.cursor()

    query = """
        SELECT b.id
        FROM bookmarks b
        LEFT JOIN categorisation_state cs ON b.id = cs.bookmark_id
        WHERE cs.bookmark_id IS NULL
        ORDER BY b.id
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    return [row['id'] for row in cursor.fetchall()]


def get_all_categories(conn: sqlite3.Connection) -> List[Dict]:
    """Load full category taxonomy.

    Args:
        conn: Database connection

    Returns:
        List of category dictionaries with id, name, parent_id, description, level
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, parent_id, description, level
        FROM categories
        ORDER BY level, name
    """)

    return [dict(row) for row in cursor.fetchall()]


def categorise_bookmark_freeform_prompt(bookmark: Dict) -> str:
    """Create prompt for free-form categorisation (no ontology constraint).

    Args:
        bookmark: Bookmark dictionary

    Returns:
        Formatted prompt string
    """
    author = bookmark.get('author_handle', 'unknown')
    if not author.startswith('@'):
        author = f"@{author}"
    content = bookmark.get('content', '')

    prompt = f"""Analyse this Twitter bookmark and suggest 1-3 categories for it.
Don't limit yourself to any predefined taxonomy - create whatever categories make sense.

BOOKMARK:
Author: {author}
Content: {content}

INSTRUCTIONS:
1. Suggest 1-3 category names that best describe this content
2. Provide confidence score (0.0-1.0) for each
3. Include brief reasoning for each category

OUTPUT FORMAT (JSON):
{{
  "suggested_categories": [
    {{"name": "Category Name", "confidence": 0.9, "reasoning": "Brief explanation"}},
    ...
  ]
}}

Respond ONLY with valid JSON. No explanations or markdown formatting."""

    return prompt


def categorise_bookmark_prompt(bookmark: Dict, categories: List[Dict]) -> str:
    """Create prompt for categorising a single bookmark.

    Args:
        bookmark: Bookmark dictionary
        categories: List of category dictionaries

    Returns:
        Formatted prompt string
    """
    # Format bookmark
    author = bookmark.get('author_handle', 'unknown')
    if not author.startswith('@'):
        author = f"@{author}"
    content = bookmark.get('content', '')

    # Format categories hierarchically
    category_lines = []
    for cat in categories:
        indent = "  " * cat['level']
        category_lines.append(f"{indent}- {cat['name']} (ID: {cat['id']}): {cat['description']}")

    categories_text = '\n'.join(category_lines)

    prompt = f"""Categorise this Twitter bookmark into the most appropriate categories.

BOOKMARK:
Author: {author}
Content: {content}

AVAILABLE CATEGORIES:
{categories_text}

INSTRUCTIONS:
1. Assign 1-3 most relevant categories (use category IDs)
2. Provide confidence score (0.0-1.0) for each assignment
3. If no good fit exists, suggest new categories with confidence scores
4. Consider hierarchy - child categories are more specific than parents

OUTPUT FORMAT (JSON):
{{
  "categories": [{{"id": 2, "confidence": 0.95}}, ...],
  "suggestions": [
    {{"name": "New Category Name", "confidence": 0.85}},
    ...
  ],
  "explanation": "Brief reasoning for assignments"
}}

Respond ONLY with valid JSON. No explanations or markdown formatting."""

    return prompt


def parse_freeform_response(response: str) -> List[CategorySuggestion]:
    """Parse free-form categorisation response.

    Args:
        response: JSON response from LLM

    Returns:
        List of CategorySuggestion objects

    Raises:
        ValueError: If response is invalid JSON or missing required fields
    """
    # Strip markdown code blocks if present
    response = response.strip()
    if response.startswith('```'):
        lines = response.split('\n')
        response = '\n'.join(lines[1:-1])

    try:
        data = json.loads(response)
        suggestions = []
        for cat in data.get('suggested_categories', []):
            suggestions.append(CategorySuggestion(
                name=cat['name'],
                confidence=cat.get('confidence', 0.5)
            ))
        return suggestions
    except (json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Invalid free-form response: {e}")


def parse_categorisation_response(response: str) -> CategorisationResult:
    """Parse LLM response into CategorisationResult.

    Args:
        response: JSON response from LLM

    Returns:
        CategorisationResult object

    Raises:
        ValueError: If response is invalid JSON or missing required fields
    """
    # Strip markdown code blocks if present
    response = response.strip()
    if response.startswith('```'):
        lines = response.split('\n')
        response = '\n'.join(lines[1:-1])

    try:
        data = json.loads(response)

        categories = [
            (cat['id'], cat.get('confidence', 1.0))
            for cat in data.get('categories', [])
        ]

        # Parse suggestions with backward compatibility
        suggestions = []
        for sug in data.get('suggestions', []):
            if isinstance(sug, dict):
                # New format: {"name": "...", "confidence": 0.85}
                suggestions.append(CategorySuggestion(
                    name=sug['name'],
                    confidence=sug.get('confidence', 0.5)
                ))
            else:
                # Backward compatibility: plain string
                suggestions.append(CategorySuggestion(
                    name=sug,
                    confidence=0.5
                ))

        explanation = data.get('explanation', '')

        return CategorisationResult(
            categories=categories,
            suggestions=suggestions,
            explanation=explanation
        )

    except (json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Invalid categorisation response: {e}")


def save_categorisation(
    conn: sqlite3.Connection,
    bookmark_id: str,
    result: CategorisationResult
) -> None:
    """Save categorisation result to database.

    Updates bookmark_categories, categorisation_state, and categorisation_log.

    Args:
        conn: Database connection
        bookmark_id: Bookmark ID
        result: CategorisationResult object
    """
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    # Insert category assignments
    for category_id, confidence in result.categories:
        cursor.execute("""
            INSERT OR REPLACE INTO bookmark_categories
            (bookmark_id, category_id, confidence, assigned_at, assigned_by)
            VALUES (?, ?, ?, ?, 'auto')
        """, (bookmark_id, category_id, confidence, now))

    # Determine status based on confidence
    min_confidence = min([c[1] for c in result.categories], default=1.0)
    status = 'needs_review' if min_confidence < CONFIDENCE_THRESHOLD else 'categorised'

    # Update categorisation state
    cursor.execute("""
        INSERT OR REPLACE INTO categorisation_state
        (bookmark_id, status, last_attempt, attempt_count)
        VALUES (?, ?, ?, 1)
    """, (bookmark_id, status, now))

    # Log low confidence
    if min_confidence < CONFIDENCE_THRESHOLD:
        cursor.execute("""
            INSERT INTO categorisation_log
            (bookmark_id, event_type, message, confidence, created_at)
            VALUES (?, 'low_confidence', ?, ?, ?)
        """, (bookmark_id, result.explanation, min_confidence, now))

    # Log suggestions
    for suggestion in result.suggestions:
        cursor.execute("""
            INSERT INTO categorisation_log
            (bookmark_id, event_type, suggested_category, confidence, created_at)
            VALUES (?, 'taxonomy_suggestion', ?, ?, ?)
        """, (bookmark_id, suggestion.name, suggestion.confidence, now))

    # Log suggestions to text file for easy review
    if result.suggestions:
        log_suggestions_to_file(bookmark_id, result.suggestions)

    conn.commit()


# Statistics

def get_categorisation_stats(conn: sqlite3.Connection) -> Dict:
    """Get categorisation statistics.

    Returns:
        Dictionary with stats: total, categorised, pending, needs_review, etc.
    """
    cursor = conn.cursor()

    # Total bookmarks
    cursor.execute("SELECT COUNT(*) as total FROM bookmarks")
    total = cursor.fetchone()['total']

    # By status
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM categorisation_state
        GROUP BY status
    """)
    by_status = {row['status']: row['count'] for row in cursor.fetchall()}

    categorised = by_status.get('categorised', 0)
    needs_review = by_status.get('needs_review', 0)
    pending = total - sum(by_status.values())

    # Categories count
    cursor.execute("SELECT COUNT(*) as count FROM categories")
    category_count = cursor.fetchone()['count']

    # Average confidence
    cursor.execute("""
        SELECT AVG(confidence) as avg_confidence
        FROM bookmark_categories
    """)
    avg_confidence = cursor.fetchone()['avg_confidence'] or 0.0

    # Review items
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM categorisation_log
        WHERE reviewed = FALSE
    """)
    review_count = cursor.fetchone()['count']

    return {
        'total': total,
        'categorised': categorised,
        'needs_review': needs_review,
        'pending': pending,
        'category_count': category_count,
        'avg_confidence': avg_confidence,
        'review_count': review_count
    }
