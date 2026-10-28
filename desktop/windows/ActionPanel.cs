using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Windows.Foundation;

namespace SmartSearch.Desktop;

// Keep native buttons at their natural sizes and wrap only when they no longer fit.
internal sealed class ActionPanel : Panel
{
    private const double Gap = 8;
    // Layout rounding can arrange the panel a fraction of a pixel narrower than it measured itself,
    // which would wrap the last button below the height the parent reserved.
    private const double RoundingTolerance = 1;

    protected override Size MeasureOverride(Size availableSize)
    {
        foreach (var child in Children) child.Measure(new Size(availableSize.Width, double.PositiveInfinity));
        return Layout(availableSize.Width, arrange: false);
    }

    protected override Size ArrangeOverride(Size finalSize)
    {
        Layout(finalSize.Width, arrange: true);
        return finalSize;
    }

    private Size Layout(double width, bool arrange)
    {
        double x = 0, y = 0, lineHeight = 0, usedWidth = 0;
        foreach (var child in Children)
        {
            if (child.Visibility == Visibility.Collapsed) continue;
            var size = child.DesiredSize;
            if (x > 0 && x + size.Width > width + RoundingTolerance)
            {
                y += lineHeight + Gap;
                x = lineHeight = 0;
            }
            if (arrange) child.Arrange(new Rect(x, y, size.Width, size.Height));
            usedWidth = Math.Max(usedWidth, x + size.Width);
            x += size.Width + Gap;
            lineHeight = Math.Max(lineHeight, size.Height);
        }
        return new Size(usedWidth, y + lineHeight);
    }
}
